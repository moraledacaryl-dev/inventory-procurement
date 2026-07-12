"""pass 1 configurable operating structure

Revision ID: 0010_operating_structure
Revises: 0009_stabilization_rollout
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_operating_structure"
down_revision = "0009_stabilization_rollout"
branch_labels = None
depends_on = None


WORKSPACES = {
    "fnb": "f19a0bb1-d94a-5bd4-aefd-e2e6051548fb",
    "hotel": "d9d5b27f-b988-514e-b8dd-d5b0cce35035",
    "assets": "a1ac8d31-96fc-51ac-9211-d6366f6737dd",
    "shared": "f0cbfd3a-85ce-545e-8856-aa5e85027d1a",
}
RECORD_CLASSES = {
    "consumable": "056d0a00-d73f-5579-aaff-176b6f6bd16e",
    "reusable": "23c7af9e-de1b-598f-9406-443c2b88c937",
    "fixed": "2628221d-0583-55ae-bc59-828b5aca1c71",
    "service": "f4e313dd-c7d6-554c-bb8f-66622f43eaed",
}


def row(id, dimension_type, code, name, behavior_key=None, parent_id=None, workspace_id=None, sort_order=0, description=None, is_system=True, settings=None):
    return {
        "id": id,
        "dimension_type": dimension_type,
        "code": code,
        "name": name,
        "description": description,
        "behavior_key": behavior_key,
        "parent_id": parent_id,
        "workspace_id": workspace_id,
        "sort_order": sort_order,
        "settings": settings or {},
        "is_system": is_system,
        "is_active": True,
    }


def upgrade():
    op.create_table(
        "operational_dimensions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dimension_type", sa.String(50), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("behavior_key", sa.String(80)),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("operational_dimensions.id")),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("operational_dimensions.id")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("settings", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("dimension_type", "code", name="uq_operational_dimension_type_code"),
    )
    for column in ("dimension_type", "code", "name", "behavior_key", "parent_id", "workspace_id"):
        op.create_index(f"ix_operational_dimensions_{column}", "operational_dimensions", [column])

    op.create_table(
        "item_workspace_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("operational_dimensions.id"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("item_id", "workspace_id", name="uq_item_workspace_assignment"),
    )
    op.create_index("ix_item_workspace_assignments_item_id", "item_workspace_assignments", ["item_id"])
    op.create_index("ix_item_workspace_assignments_workspace_id", "item_workspace_assignments", ["workspace_id"])

    with op.batch_alter_table("categories") as batch:
        batch.add_column(sa.Column("parent_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
        batch.create_foreign_key("fk_categories_parent_id", "categories", ["parent_id"], ["id"])
        batch.create_index("ix_categories_parent_id", ["parent_id"])

    with op.batch_alter_table("items") as batch:
        for name in ("record_class_id", "item_type_id", "primary_workspace_id", "department_id", "cost_center_id"):
            batch.add_column(sa.Column(name, sa.String(36), nullable=True))
            batch.create_foreign_key(f"fk_items_{name}", "operational_dimensions", [name], ["id"])
            batch.create_index(f"ix_items_{name}", [name])
        batch.add_column(sa.Column("default_location_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_items_default_location_id", "locations", ["default_location_id"], ["id"])
        batch.create_index("ix_items_default_location_id", ["default_location_id"])

    dimensions = [
        row(WORKSPACES["fnb"], "workspace", "fnb", "F&B", "fnb", sort_order=10),
        row(WORKSPACES["hotel"], "workspace", "hotel", "Hotel", "hotel", sort_order=20),
        row(WORKSPACES["assets"], "workspace", "assets-property", "Assets & Property", "assets", sort_order=30),
        row(WORKSPACES["shared"], "workspace", "shared-operations", "Shared Operations", "shared", sort_order=40),
        row(RECORD_CLASSES["consumable"], "record_class", "consumable", "Consumable inventory", "stock_consumable", sort_order=10),
        row(RECORD_CLASSES["reusable"], "record_class", "reusable-property", "Reusable operating property", "reusable_property", sort_order=20),
        row(RECORD_CLASSES["fixed"], "record_class", "fixed-asset", "Fixed asset", "fixed_asset", sort_order=30),
        row(RECORD_CLASSES["service"], "record_class", "service-expense", "Non-stock expense or service", "service_expense", sort_order=40),
        row("88891a22-7575-5a56-804f-eaf2f3cf2ff7", "business_unit", "hidden-oasis", "Hidden Oasis", "operating_entity", sort_order=10),
        row("ac69261c-c552-5779-a80f-8d2e72dcb602", "item_type", "ingredient", "Ingredient", "ingredient", RECORD_CLASSES["consumable"], WORKSPACES["fnb"], 10),
        row("20c126f7-76c1-593a-886f-86cb30154cf5", "item_type", "beverage-ingredient", "Beverage ingredient", "ingredient", RECORD_CLASSES["consumable"], WORKSPACES["fnb"], 20),
        row("6b9566d5-fe47-5bbb-9afa-ebfdc2dde0ab", "item_type", "prep-item", "Prep or sub-recipe item", "recipe_output", RECORD_CLASSES["consumable"], WORKSPACES["fnb"], 30),
        row("bc3b124d-b37a-5ca3-ac34-c15d450a318a", "item_type", "finished-fnb-product", "Finished F&B product", "recipe_output", RECORD_CLASSES["consumable"], WORKSPACES["fnb"], 40),
        row("d4f9f1ad-6448-529d-a11e-4fbf38c37535", "item_type", "recipe-packaging", "Recipe packaging", "recipe_packaging", RECORD_CLASSES["consumable"], WORKSPACES["fnb"], 50),
        row("d23cccac-3a05-5d51-b61e-60f37b0776e5", "item_type", "guest-amenity", "Guest amenity", "hotel_consumable", RECORD_CLASSES["consumable"], WORKSPACES["hotel"], 10),
        row("745a580c-c962-59e1-8fe4-9443026b5681", "item_type", "housekeeping-supply", "Housekeeping supply", "hotel_consumable", RECORD_CLASSES["consumable"], WORKSPACES["hotel"], 20),
        row("6cd1c0fa-7878-5198-91f7-8c05785e7043", "item_type", "linen", "Linen", "reusable_property", RECORD_CLASSES["reusable"], WORKSPACES["hotel"], 30),
        row("8fe51424-2c6c-53e8-ac3f-b0b603064b4c", "item_type", "maintenance-supply", "Maintenance supply", "stock_consumable", RECORD_CLASSES["consumable"], WORKSPACES["shared"], 10),
        row("edc0841b-341c-5c86-9c06-ce7f5ede33e6", "item_type", "equipment", "Equipment", "fixed_asset", RECORD_CLASSES["fixed"], WORKSPACES["assets"], 10),
        row("7ef58b61-c15f-51d2-b015-b459683fe3fb", "item_type", "general-consumable", "General consumable", "stock_consumable", RECORD_CLASSES["consumable"], WORKSPACES["shared"], 20),
        row("94ff9486-85b7-534c-b05a-fdbf73e17d2b", "item_type", "service", "Service or direct expense", "service_expense", RECORD_CLASSES["service"], WORKSPACES["shared"], 30),
        row("c6860295-82db-51f9-ac1b-a5fd129a7b60", "department", "cafe", "Café", "outlet", workspace_id=WORKSPACES["fnb"], sort_order=10),
        row("80a42b54-066f-5520-b564-e9119a1d578b", "department", "restaurant", "Restaurant", "outlet", workspace_id=WORKSPACES["fnb"], sort_order=20),
        row("e96fe218-72bb-5708-ab0b-39091e260800", "department", "bar", "Bar", "outlet", workspace_id=WORKSPACES["fnb"], sort_order=30),
        row("5440d704-0ea2-59e6-bdba-efdb9fc8ca65", "department", "kitchen", "Main Kitchen", "department", workspace_id=WORKSPACES["fnb"], sort_order=40),
        row("3fe95ab0-782b-5073-900f-570cdbc9536e", "department", "housekeeping", "Housekeeping", "department", workspace_id=WORKSPACES["hotel"], sort_order=10),
        row("81e728c5-8757-5c78-8115-b4ade79df040", "department", "front-office", "Front Office", "department", workspace_id=WORKSPACES["hotel"], sort_order=20),
        row("1f477993-9b42-5e48-a6ee-216f1c5b600c", "department", "maintenance", "Maintenance", "department", workspace_id=WORKSPACES["shared"], sort_order=10),
        row("cb15ddef-b290-5991-979c-339db7d808ef", "department", "laundry", "Laundry", "department", workspace_id=WORKSPACES["hotel"], sort_order=30),
        row("e8d816da-1699-5133-9971-d6402924b6bc", "department", "administration", "Administration", "department", workspace_id=WORKSPACES["shared"], sort_order=20),
        row("4909da61-7a07-5ae6-94f2-fcbe7ec3f828", "cost_center", "fnb", "F&B", "cost_center", workspace_id=WORKSPACES["fnb"], sort_order=10),
        row("04ca09c7-434d-5f98-9a87-50b12923f041", "cost_center", "hotel", "Hotel", "cost_center", workspace_id=WORKSPACES["hotel"], sort_order=20),
        row("7595046f-d207-5fb6-85ea-2c0b0dfb5cfe", "cost_center", "assets-property", "Assets & Property", "cost_center", workspace_id=WORKSPACES["assets"], sort_order=30),
        row("54c8eb1d-c3e6-5082-adbb-efe7d8a5c071", "cost_center", "shared-operations", "Shared Operations", "cost_center", workspace_id=WORKSPACES["shared"], sort_order=40),
        row("f132ec66-10b9-5635-a79b-24e11402da74", "location_type", "storeroom", "Storeroom", "stock_location", sort_order=10),
        row("8584697b-3c65-54ca-b231-4de8b2988dd3", "location_type", "kitchen", "Kitchen", "stock_location", sort_order=20),
        row("551e0633-f398-5c9f-9f33-3a207f164487", "location_type", "bar", "Bar", "stock_location", sort_order=30),
        row("c740f01b-48c0-5865-b7ef-cfb23f144f65", "location_type", "housekeeping", "Housekeeping store", "stock_location", sort_order=40),
        row("2a6c97d5-a14f-5664-a773-7027050224bf", "location_type", "linen", "Linen room", "property_location", sort_order=50),
        row("e5c568ba-652d-5b34-9c19-17f33308a5ad", "location_type", "maintenance", "Maintenance store", "property_location", sort_order=60),
        row("52155fb0-73b1-512d-9781-88616ef91aa7", "asset_class", "equipment", "Equipment", "depreciable_asset", sort_order=10),
        row("c1c9b70c-8cfa-5649-94db-266ddf403496", "asset_class", "furniture", "Furniture and fixtures", "depreciable_asset", sort_order=20),
        row("06e3a1a8-a9ef-546c-b02a-32b37e3bb6cc", "asset_class", "vehicle", "Vehicles", "depreciable_asset", sort_order=30),
        row("cbfd63c2-7df1-53c3-afdd-6e8ed9f2ddfe", "depreciation_method", "straight-line", "Straight-line", "straight_line", sort_order=10),
        row("b883f3eb-3064-554f-85dd-c5f13afcd580", "depreciation_method", "none", "No depreciation", "none", sort_order=20),
    ]
    condition_names = [
        ("f3601e31-605f-5d7f-a1b0-265ccdc99bb4", "available", "Available", 10),
        ("4d428471-33b4-59a0-bf0e-712faddc1b3b", "issued", "Issued", 20),
        ("6f2f631f-ab4f-538b-8f6c-811ade280835", "in-use", "In use", 30),
        ("672b2857-2b1e-59ab-a764-95f09f79900e", "laundry", "In laundry", 40),
        ("80e61de4-4cbb-5237-83ab-e6f6fade0920", "repair", "In repair", 50),
        ("a36e9fbe-5fb2-5aa2-b575-b412ae6dc794", "damaged", "Damaged", 60),
        ("35d922c4-40c5-586f-a5f1-2e7fd778c60f", "lost", "Lost", 70),
        ("a272d291-857c-5256-b680-86e247590d16", "retired", "Retired", 80),
    ]
    dimensions += [row(id, "condition_status", code, name, code.replace("-", "_"), sort_order=order) for id, code, name, order in condition_names]
    movement_names = [
        ("b772829b-e325-5119-844b-76e005af42dc", "consumption", "Consumption", 10),
        ("37078139-8eee-54f0-be81-754b6ea0bc27", "waste", "Waste", 20),
        ("6c883004-6a38-5800-afb3-c4340b040699", "damage", "Damage", 30),
        ("f0f2becf-2807-5538-97e0-34055b3244cc", "transfer", "Transfer", 40),
        ("a42b36c5-99dc-5783-aef2-f76edc236289", "count-variance", "Count variance", 50),
    ]
    dimensions += [row(id, "movement_reason", code, name, code.replace("-", "_"), sort_order=order) for id, code, name, order in movement_names]

    table = sa.table(
        "operational_dimensions",
        sa.column("id", sa.String), sa.column("dimension_type", sa.String), sa.column("code", sa.String),
        sa.column("name", sa.String), sa.column("description", sa.Text), sa.column("behavior_key", sa.String),
        sa.column("parent_id", sa.String), sa.column("workspace_id", sa.String), sa.column("sort_order", sa.Integer),
        sa.column("settings", sa.JSON), sa.column("is_system", sa.Boolean), sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(table, dimensions)


def downgrade():
    with op.batch_alter_table("items") as batch:
        batch.drop_index("ix_items_default_location_id")
        batch.drop_constraint("fk_items_default_location_id", type_="foreignkey")
        batch.drop_column("default_location_id")
        for name in reversed(("record_class_id", "item_type_id", "primary_workspace_id", "department_id", "cost_center_id")):
            batch.drop_index(f"ix_items_{name}")
            batch.drop_constraint(f"fk_items_{name}", type_="foreignkey")
            batch.drop_column(name)
    with op.batch_alter_table("categories") as batch:
        batch.drop_index("ix_categories_parent_id")
        batch.drop_constraint("fk_categories_parent_id", type_="foreignkey")
        batch.drop_column("sort_order")
        batch.drop_column("parent_id")
    op.drop_table("item_workspace_assignments")
    op.drop_table("operational_dimensions")
