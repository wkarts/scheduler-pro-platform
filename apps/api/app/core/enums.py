from enum import StrEnum


class TenantStatus(StrEnum):
    pending = "PENDING"
    provisioning = "PROVISIONING"
    active = "ACTIVE"
    suspended = "SUSPENDED"
    failed = "FAILED"
    deleting = "DELETING"
    deleted = "DELETED"


class ProvisioningStepStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class AppointmentStatus(StrEnum):
    pending = "PENDING"
    awaiting_confirmation = "AWAITING_CONFIRMATION"
    confirmed = "CONFIRMED"
    checked_in = "CHECKED_IN"
    in_progress = "IN_PROGRESS"
    completed = "COMPLETED"
    cancelled = "CANCELLED"
    no_show = "NO_SHOW"


class LandingPageStatus(StrEnum):
    draft = "DRAFT"
    published = "PUBLISHED"
    archived = "ARCHIVED"


class BuildStatus(StrEnum):
    queued = "QUEUED"
    preparing = "PREPARING"
    building = "BUILDING"
    signing = "SIGNING"
    uploading = "UPLOADING"
    completed = "COMPLETED"
    failed = "FAILED"
    cancelled = "CANCELLED"
