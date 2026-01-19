"""
URL routing for intake sessions.
"""
from django.urls import path
from apps.intake.views import (
    IntakeSessionListCreateView,
    IntakeSessionDetailView,
    IntakeSessionStatusView,
    IntakeMessageSendView,
    IntakeMessageRetryView,
    IntakeSessionMessagesView,
    IntakeSessionProposalsView,
    IntakeSessionProgressView,
    ProposalApplyView,
    ProposalApplyMultipleView,
    ProposalRejectView,
    IntakeSessionFactStatusView,
    IntakeSessionOutputView,
    IntakeSessionOutcomeView,
    IntakeOutcomeByPropertyView,
)

app_name = "intake"

urlpatterns = [
    # Session management
    path(
        "intake/sessions/",
        IntakeSessionListCreateView.as_view(),
        name="session-list-create"
    ),
    path(
        "intake/sessions/<uuid:session_id>/",
        IntakeSessionDetailView.as_view(),
        name="session-detail"
    ),
    path(
        "intake/sessions/<uuid:session_id>/status/",
        IntakeSessionStatusView.as_view(),
        name="session-status"
    ),
    
    # Messaging
    path(
        "intake/sessions/<uuid:session_id>/messages/",
        IntakeSessionMessagesView.as_view(),
        name="session-messages"
    ),
    path(
        "intake/sessions/<uuid:session_id>/send/",
        IntakeMessageSendView.as_view(),
        name="session-send"
    ),
    path(
        "intake/sessions/<uuid:session_id>/messages/<uuid:message_id>/retry/",
        IntakeMessageRetryView.as_view(),
        name="message-retry"
    ),
    
    # Proposals & Progress
    path(
        "intake/sessions/<uuid:session_id>/proposals/",
        IntakeSessionProposalsView.as_view(),
        name="session-proposals"
    ),
    path(
        "intake/sessions/<uuid:session_id>/progress/",
        IntakeSessionProgressView.as_view(),
        name="session-progress"
    ),
    path(
        "intake/sessions/<uuid:session_id>/fact-status/",
        IntakeSessionFactStatusView.as_view(),
        name="session-fact-status"
    ),
    path(
        "intake/sessions/<uuid:session_id>/output/",
        IntakeSessionOutputView.as_view(),
        name="session-output"
    ),
    
    # Outcome (for consumption by other systems)
    path(
        "intake/sessions/<uuid:session_id>/outcome/",
        IntakeSessionOutcomeView.as_view(),
        name="session-outcome"
    ),
    path(
        "intake/property/<uuid:property_id>/outcome/",
        IntakeOutcomeByPropertyView.as_view(),
        name="property-outcome"
    ),
    
    # Proposal management
    path(
        "intake/sessions/<uuid:session_id>/proposals/<uuid:proposal_id>/apply/",
        ProposalApplyView.as_view(),
        name="proposal-apply"
    ),
    path(
        "intake/sessions/<uuid:session_id>/proposals/apply-multiple/",
        ProposalApplyMultipleView.as_view(),
        name="proposals-apply-multiple"
    ),
    path(
        "intake/sessions/<uuid:session_id>/proposals/<uuid:proposal_id>/reject/",
        ProposalRejectView.as_view(),
        name="proposal-reject"
    ),
]
