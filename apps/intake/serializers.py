"""
Serializers for intake session API.
"""
from rest_framework import serializers
from apps.intake.models import (
    IntakeSession,
    IntakeSessionStatus,
    IntakeMessage,
    MessageRole,
    UpdateProposal,
    UpdateProposalStatus,
)


class MediaAttachmentSerializer(serializers.Serializer):
    """Serializer for media attachment references."""
    blob_name = serializers.CharField(max_length=500)
    content_type = serializers.CharField(max_length=100)
    file_name = serializers.CharField(max_length=255)


class IntakeMessageSerializer(serializers.ModelSerializer):
    """Serializer for intake messages."""
    media_attachments = MediaAttachmentSerializer(many=True, read_only=True)
    in_reply_to_id = serializers.UUIDField(
        source="in_reply_to.id", 
        read_only=True, 
        allow_null=True
    )
    
    class Meta:
        model = IntakeMessage
        fields = [
            "id",
            "role",
            "content",
            "media_attachments",
            "in_reply_to_id",
            "sequence_number",
            "created_at",
        ]
        read_only_fields = fields


class UpdateProposalSerializer(serializers.ModelSerializer):
    """Serializer for update proposals."""
    proposal_type_display = serializers.CharField(
        source="get_proposal_type_display",
        read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True
    )
    
    class Meta:
        model = UpdateProposal
        fields = [
            "id",
            "proposal_type",
            "proposal_type_display",
            "status",
            "status_display",
            "target_entity_id",
            "target_entity_type",
            "proposed_data",
            "summary",
            "created_at",
        ]
        read_only_fields = fields


class OnboardingProgressSerializer(serializers.Serializer):
    """Serializer for onboarding progress."""
    property_type = serializers.CharField()
    overall_completion = serializers.FloatField()
    required_completion = serializers.FloatField()
    categories = serializers.DictField()
    missing_required = serializers.ListField(child=serializers.CharField())
    missing_important = serializers.ListField(child=serializers.CharField())
    suggested_next_topic = serializers.CharField(allow_null=True)
    suggested_next_fields = serializers.ListField(child=serializers.CharField())


class IntakeSessionSerializer(serializers.ModelSerializer):
    """Serializer for intake sessions."""
    property_id = serializers.UUIDField(
        source="property.id", 
        read_only=True, 
        allow_null=True
    )
    property_address = serializers.CharField(
        source="property.address", 
        read_only=True, 
        allow_null=True
    )
    status_display = serializers.CharField(
        source="get_status_display", 
        read_only=True
    )
    
    class Meta:
        model = IntakeSession
        fields = [
            "id",
            "title",
            "status",
            "status_display",
            "property_id",
            "property_address",
            "message_count",
            "last_message_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class IntakeSessionDetailSerializer(IntakeSessionSerializer):
    """Detailed serializer including messages, proposals, and progress."""
    messages = IntakeMessageSerializer(many=True, read_only=True)
    pending_proposals = UpdateProposalSerializer(many=True, read_only=True)
    onboarding_progress = serializers.SerializerMethodField()
    
    class Meta(IntakeSessionSerializer.Meta):
        fields = IntakeSessionSerializer.Meta.fields + [
            "messages",
            "pending_proposals",
            "onboarding_progress",
        ]
    
    def get_onboarding_progress(self, obj):
        from apps.intake.services import IntakeSessionService
        progress = IntakeSessionService.get_onboarding_progress(obj)
        return progress.to_dict()


class CreateSessionRequestSerializer(serializers.Serializer):
    """Request serializer for creating a session."""
    property_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    auto_greet = serializers.BooleanField(default=True)


class SendMessageRequestSerializer(serializers.Serializer):
    """Request serializer for sending a message."""
    content = serializers.CharField(min_length=1, max_length=10000)
    media_attachments = MediaAttachmentSerializer(many=True, required=False)


class SendMessageResponseSerializer(serializers.Serializer):
    """Response serializer for send message endpoint."""
    user_message = IntakeMessageSerializer()
    assistant_message = IntakeMessageSerializer()
    new_proposals = UpdateProposalSerializer(many=True)
    onboarding_progress = OnboardingProgressSerializer()


class ApplyProposalRequestSerializer(serializers.Serializer):
    """Request serializer for applying a proposal."""
    proposal_id = serializers.UUIDField(required=True)


class ApplyMultipleProposalsRequestSerializer(serializers.Serializer):
    """Request serializer for applying multiple proposals."""
    proposal_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=50,
    )


class RejectProposalRequestSerializer(serializers.Serializer):
    """Request serializer for rejecting a proposal."""
    reason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="Optional reason for rejection"
    )


class ProposalApplicationResultSerializer(serializers.Serializer):
    """Serializer for proposal application result."""
    success = serializers.BooleanField()
    entity_type = serializers.CharField(allow_null=True)
    entity_id = serializers.UUIDField(allow_null=True)
    message = serializers.CharField()


class ApplyProposalsResponseSerializer(serializers.Serializer):
    """Response serializer for applying proposals."""
    successful = ProposalApplicationResultSerializer(many=True)
    failed = serializers.ListField(
        child=serializers.DictField()
    )
    total = serializers.IntegerField()


# Outcome serializers
class PropertyDetailsSerializer(serializers.Serializer):
    """Serializer for property details in outcome."""
    id = serializers.CharField()
    address = serializers.CharField()
    address_line_1 = serializers.CharField(allow_null=True)
    city = serializers.CharField(allow_null=True)
    state = serializers.CharField(allow_null=True)
    zip_code = serializers.CharField(allow_null=True)
    property_type = serializers.CharField(allow_null=True)
    square_feet = serializers.IntegerField(allow_null=True)
    bedrooms = serializers.IntegerField(allow_null=True)
    bathrooms = serializers.FloatField(allow_null=True)
    num_floors = serializers.IntegerField(allow_null=True)
    year_built = serializers.IntegerField(allow_null=True)
    access_instructions = serializers.CharField(allow_null=True)
    parking_instructions = serializers.CharField(allow_null=True)


class RoomInfoSerializer(serializers.Serializer):
    """Serializer for room info in outcome."""
    name = serializers.CharField()
    display_name = serializers.CharField()
    notes = serializers.ListField(child=serializers.CharField())
    surfaces = serializers.ListField(child=serializers.CharField())


class StandardRuleSerializer(serializers.Serializer):
    """Serializer for do/don't rules."""
    id = serializers.CharField()
    rule_type = serializers.CharField()
    content = serializers.CharField()
    room_name = serializers.CharField(allow_null=True)
    surface_name = serializers.CharField(allow_null=True)
    priority = serializers.IntegerField()


class ProductPreferenceSerializer(serializers.Serializer):
    """Serializer for product preferences."""
    id = serializers.CharField()
    product_name = serializers.CharField()
    use_product = serializers.BooleanField()
    notes = serializers.CharField(allow_null=True)
    room_name = serializers.CharField(allow_null=True)


class SensitivitySerializer(serializers.Serializer):
    """Serializer for sensitivities."""
    id = serializers.CharField()
    content = serializers.CharField()
    severity = serializers.CharField(allow_null=True)


class GeneralNoteSerializer(serializers.Serializer):
    """Serializer for general notes."""
    id = serializers.CharField()
    content = serializers.CharField()
    room_name = serializers.CharField(allow_null=True)
    surface_name = serializers.CharField(allow_null=True)
    label = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)


class StandardsSummarySerializer(serializers.Serializer):
    """Summary counts for standards."""
    total_rules = serializers.IntegerField()
    total_product_preferences = serializers.IntegerField()
    total_sensitivities = serializers.IntegerField()
    total_notes = serializers.IntegerField()


class StandardsSerializer(serializers.Serializer):
    """Serializer for all standards."""
    do_rules = StandardRuleSerializer(many=True)
    dont_rules = StandardRuleSerializer(many=True)
    product_preferences = ProductPreferenceSerializer(many=True)
    sensitivities = SensitivitySerializer(many=True)
    general_notes = GeneralNoteSerializer(many=True)
    summary = StandardsSummarySerializer()


class MissingInfoSerializer(serializers.Serializer):
    """Serializer for missing info."""
    categories = serializers.ListField(child=serializers.CharField())
    details = serializers.DictField()


class ReadinessInfoSerializer(serializers.Serializer):
    """Serializer for readiness status."""
    status = serializers.CharField()
    is_ready = serializers.BooleanField()
    completion_percentage = serializers.FloatField()
    missing = MissingInfoSerializer(allow_null=True, required=False)


class SessionInfoSerializer(serializers.Serializer):
    """Serializer for session info in outcome."""
    id = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class IntakeOutcomeSerializer(serializers.Serializer):
    """
    Serializer for the complete intake outcome.
    
    This is the main response format for the outcome endpoint.
    """
    session = SessionInfoSerializer()
    property_id = serializers.CharField(allow_null=True)
    has_property = serializers.BooleanField()
    property = PropertyDetailsSerializer(allow_null=True)
    rooms = RoomInfoSerializer(many=True)
    standards = StandardsSerializer()
    readiness = ReadinessInfoSerializer()
    generated_at = serializers.DateTimeField()