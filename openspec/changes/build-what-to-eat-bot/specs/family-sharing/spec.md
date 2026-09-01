## ADDED Requirements

### Requirement: Family catalog
The system SHALL let users create or join one family and see all current members' dishes, favorites, searches, and recommendations with author attribution.

#### Scenario: Shared visibility
- **WHEN** two users are current members of one family
- **THEN** each sees both members' dishes while unrelated users see neither

### Requirement: Secure invitations
The system SHALL create high-entropy, hashed, expiring, single-use invitation tokens and require explicit join confirmation.

#### Scenario: Expired or reused invite
- **WHEN** a user tries an expired, invalid, or accepted invitation
- **THEN** joining is rejected without revealing sensitive token details

### Requirement: Leave family
The system SHALL transactionally remove a member while preserving authored dishes and revoking access to other members' dishes.

#### Scenario: Member leaves
- **WHEN** a member confirms leaving a family
- **THEN** the member retains personal dishes and immediately loses access to dishes authored by remaining members
