import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import Stripe from 'https://esm.sh/stripe@13.10.0?target=deno'

serve(async (req) => {
  try {
    // Initialize Stripe
    const stripe = new Stripe(Deno.env.get('STRIPE_SECRET_KEY') || '', {
      apiVersion: '2023-10-16',
      httpClient: Stripe.createFetchHttpClient(),
    })

    // Initialize Supabase client
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    const supabaseClient = createClient(supabaseUrl, supabaseServiceKey)

    // Verify webhook signature
    const signature = req.headers.get('stripe-signature')
    const webhookSecret = Deno.env.get('STRIPE_WEBHOOK_SECRET')
    
    if (!signature || !webhookSecret) {
      throw new Error('Missing signature or webhook secret')
    }

    const body = await req.text()
    
    let event: Stripe.Event
    try {
      event = stripe.webhooks.constructEvent(body, signature, webhookSecret)
    } catch (err) {
      return new Response(
        JSON.stringify({ error: 'Invalid signature' }),
        { status: 400 }
      )
    }

    // Store the webhook event for audit trail
    const { data: webhookEvent, error: webhookError } = await supabaseClient
      .from('webhook_events')
      .insert({
        source: 'stripe',
        event_type: event.type,
        payload: event,
        correlation_id: event.id,
        status: 'processing'
      })
      .select()
      .single()

    if (webhookError) {
      throw new Error('Failed to store webhook event')
    }

    try {
      // Handle specific event types
      switch (event.type) {
        case 'invoice.payment_succeeded':
          await handleInvoicePaymentSucceeded(event, supabaseClient)
          break
        
        case 'customer.subscription.updated':
          await handleSubscriptionUpdated(event, supabaseClient)
          break
        
        default:
          // Mark as ignored for unhandled event types
          await supabaseClient
            .from('webhook_events')
            .update({ status: 'ignored' })
            .eq('id', webhookEvent.id)
      }

      // Mark webhook as processed
      await supabaseClient
        .from('webhook_events')
        .update({ 
          status: 'processed',
          processed_at: new Date().toISOString()
        })
        .eq('id', webhookEvent.id)

    } catch (processError) {
      // Mark webhook as failed
      await supabaseClient
        .from('webhook_events')
        .update({ 
          status: 'failed',
          error_message: processError.message
        })
        .eq('id', webhookEvent.id)
      
      throw processError
    }

    return new Response(
      JSON.stringify({ received: true }),
      { status: 200 }
    )
  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 400 }
    )
  }
})

async function handleInvoicePaymentSucceeded(
  event: Stripe.Event,
  supabaseClient: any
) {
  const invoice = event.data.object as Stripe.Invoice
  const subscriptionId = invoice.subscription as string
  const customerId = invoice.customer as string
  
  // Get subscription metadata
  const subscription = await Stripe(Deno.env.get('STRIPE_SECRET_KEY')!).subscriptions.retrieve(subscriptionId)
  const userId = subscription.metadata.supabase_user_id
  const planId = subscription.metadata.plan_id
  
  if (!userId || !planId) {
    throw new Error('Missing user or plan metadata in subscription')
  }

  // Check for existing ledger entry with this invoice ID (idempotency)
  const { data: existingEntry } = await supabaseClient
    .from('ledger_entries')
    .select('id')
    .eq('correlation_reference_id', invoice.id)
    .single()

  if (existingEntry) {
    console.log(`Invoice ${invoice.id} already processed, skipping`)
    return
  }

  // Create or update membership
  const { data: membership, error: membershipError } = await supabaseClient
    .from('memberships')
    .upsert({
      user_id: userId,
      plan_id: planId,
      stripe_subscription_id: subscriptionId,
      stripe_customer_id: customerId,
      status: 'active',
      started_at: new Date(subscription.current_period_start * 1000).toISOString(),
      expires_at: new Date(subscription.current_period_end * 1000).toISOString(),
    }, {
      onConflict: 'stripe_subscription_id',
      ignoreDuplicates: false
    })
    .select()
    .single()

  if (membershipError) {
    throw new Error(`Failed to upsert membership: ${membershipError.message}`)
  }

  // Calculate credit amount (convert from cents to dollars)
  const creditAmount = invoice.amount_paid / 100

  // Create ledger entry for membership credit
  const { error: ledgerError } = await supabaseClient
    .from('ledger_entries')
    .insert({
      user_id: userId,
      source: 'stripe_subscription',
      type: 'credit',
      amount: creditAmount,
      unit_type: 'currency',
      entitlement_code: 'membership_credit',
      correlation_reference_id: invoice.id,
      metadata: {
        stripe_invoice_id: invoice.id,
        stripe_subscription_id: subscriptionId,
        billing_period_start: subscription.current_period_start,
        billing_period_end: subscription.current_period_end,
        plan_id: planId
      }
    })

  if (ledgerError) {
    throw new Error(`Failed to create ledger entry: ${ledgerError.message}`)
  }
}

async function handleSubscriptionUpdated(
  event: Stripe.Event,
  supabaseClient: any
) {
  const subscription = event.data.object as Stripe.Subscription
  const userId = subscription.metadata.supabase_user_id
  
  if (!userId) {
    console.log('No user ID in subscription metadata, skipping')
    return
  }

  // Map Stripe status to our membership status
  let membershipStatus: string
  switch (subscription.status) {
    case 'active':
    case 'trialing':
      membershipStatus = 'active'
      break
    case 'canceled':
    case 'incomplete_expired':
      membershipStatus = 'canceled'
      break
    case 'past_due':
    case 'unpaid':
      membershipStatus = 'suspended'
      break
    default:
      membershipStatus = 'suspended'
  }

  // Update membership status
  const { error } = await supabaseClient
    .from('memberships')
    .update({
      status: membershipStatus,
      expires_at: new Date(subscription.current_period_end * 1000).toISOString(),
      canceled_at: subscription.canceled_at 
        ? new Date(subscription.canceled_at * 1000).toISOString() 
        : null,
    })
    .eq('stripe_subscription_id', subscription.id)

  if (error) {
    throw new Error(`Failed to update membership status: ${error.message}`)
  }
}
