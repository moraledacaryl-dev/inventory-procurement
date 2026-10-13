import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import require_permission
from app.db.session import get_db
from app.models.pos_rules import PosModifierTemplate, PosPricingRule
from app.models.user import User
from app.services.controls import add_audit

router=APIRouter(tags=["pos-rules"])

class PricingRuleIn(BaseModel):
    name:str=Field(min_length=1,max_length=180)
    qualifier_tag:str=Field(min_length=1,max_length=80,pattern=r"^[a-z0-9][a-z0-9_-]*$")
    target_tag:str=Field(min_length=1,max_length=80,pattern=r"^[a-z0-9][a-z0-9_-]*$")
    priority:int=Field(default=100,ge=0,le=10000)
    is_active:bool=True

class ModifierOptionIn(BaseModel):
    id:str|None=Field(default=None,max_length=80,pattern=r"^[a-z0-9][a-z0-9_-]*$")
    label:str=Field(min_length=1,max_length=120)
    price_delta:float=Field(default=0,ge=0)
    is_active:bool=True

class ModifierGroupIn(BaseModel):
    id:str=Field(min_length=1,max_length=80,pattern=r"^[a-z0-9][a-z0-9_-]*$")
    label:str=Field(min_length=1,max_length=120)
    mode:str=Field(pattern=r"^(single|multi)$")
    min_selections:int=Field(default=0,ge=0)
    max_selections:int|None=Field(default=None,ge=1)
    options:list[ModifierOptionIn]=Field(min_length=1)
    @model_validator(mode="after")
    def validate_group(self):
        if self.max_selections is not None and self.min_selections>self.max_selections:
            raise ValueError("Minimum selections cannot exceed maximum selections")
        if self.mode=="single" and (self.max_selections or 1)>1:
            raise ValueError("Single-select groups cannot allow more than one selection")
        ids=[x.id for x in self.options if x.id]
        if len(ids)!=len(set(ids)):
            raise ValueError("Modifier option IDs must be unique")
        labels=[x.label.strip().casefold() for x in self.options]
        if len(labels)!=len(set(labels)):
            raise ValueError("Modifier option names must be unique")
        return self

class ModifierTemplateIn(BaseModel):
    name:str=Field(min_length=1,max_length=180)
    group:ModifierGroupIn
    is_active:bool=True

def rule_out(x):
    return {"id":x.id,"name":x.name,"qualifier_tag":x.qualifier_tag,"target_tag":x.target_tag,"priority":getattr(x,"priority",100),"is_active":x.is_active}

def modifier_out(x):
    return {"id":x.id,"name":x.name,"group":json.loads(x.config_json),"is_active":x.is_active}

def commit_or_conflict(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,"A POS rule or modifier template with that name already exists")

@router.get("/fnb/pos-rules")
def list_rules(db:Session=Depends(get_db),_:User=Depends(require_permission("items.read"))):
    return {
        "pricing_rules":[rule_out(x) for x in db.scalars(select(PosPricingRule).order_by(PosPricingRule.name)).all()],
        "modifier_templates":[modifier_out(x) for x in db.scalars(select(PosModifierTemplate).order_by(PosModifierTemplate.name)).all()],
        "conflict_policy":"lowest_price_then_priority_then_rule_id",
    }

@router.post("/fnb/pos-rules/pricing",status_code=201)
def create_rule(payload:PricingRuleIn,db:Session=Depends(get_db),user:User=Depends(require_permission("items.*"))):
    row=PosPricingRule(name=payload.name.strip(),qualifier_tag=payload.qualifier_tag,target_tag=payload.target_tag,is_active=payload.is_active)
    if hasattr(row,"priority"): row.priority=payload.priority
    db.add(row);db.flush();add_audit(db,actor_user_id=user.id,action="pos.pricing_rule_created",entity_type="pos_pricing_rule",entity_id=row.id,details=rule_out(row));commit_or_conflict(db);return rule_out(row)

@router.put("/fnb/pos-rules/pricing/{rule_id}")
def update_rule(rule_id:str,payload:PricingRuleIn,db:Session=Depends(get_db),user:User=Depends(require_permission("items.*"))):
    row=db.get(PosPricingRule,rule_id)
    if not row: raise HTTPException(404,"Pricing rule not found")
    row.name=payload.name.strip();row.qualifier_tag=payload.qualifier_tag;row.target_tag=payload.target_tag;row.is_active=payload.is_active
    if hasattr(row,"priority"): row.priority=payload.priority
    add_audit(db,actor_user_id=user.id,action="pos.pricing_rule_updated",entity_type="pos_pricing_rule",entity_id=row.id,details=rule_out(row));commit_or_conflict(db);return rule_out(row)

@router.post("/fnb/pos-rules/modifiers",status_code=201)
def create_modifier(payload:ModifierTemplateIn,db:Session=Depends(get_db),user:User=Depends(require_permission("items.*"))):
    row=PosModifierTemplate(name=payload.name.strip(),config_json=json.dumps(payload.group.model_dump(exclude_none=True)),is_active=payload.is_active)
    db.add(row);db.flush();add_audit(db,actor_user_id=user.id,action="pos.modifier_template_created",entity_type="pos_modifier_template",entity_id=row.id,details={"name":row.name});commit_or_conflict(db);return modifier_out(row)

@router.put("/fnb/pos-rules/modifiers/{template_id}")
def update_modifier(template_id:str,payload:ModifierTemplateIn,db:Session=Depends(get_db),user:User=Depends(require_permission("items.*"))):
    row=db.get(PosModifierTemplate,template_id)
    if not row: raise HTTPException(404,"Modifier template not found")
    row.name=payload.name.strip();row.config_json=json.dumps(payload.group.model_dump(exclude_none=True));row.is_active=payload.is_active
    add_audit(db,actor_user_id=user.id,action="pos.modifier_template_updated",entity_type="pos_modifier_template",entity_id=row.id,details={"name":row.name});commit_or_conflict(db);return modifier_out(row)
