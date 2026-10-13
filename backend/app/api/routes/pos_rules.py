import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
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
    is_active:bool=True

class ModifierTemplateIn(BaseModel):
    name:str=Field(min_length=1,max_length=180)
    group:dict
    is_active:bool=True

def rule_out(x):
    return {"id":x.id,"name":x.name,"qualifier_tag":x.qualifier_tag,"target_tag":x.target_tag,"is_active":x.is_active}

def modifier_out(x):
    return {"id":x.id,"name":x.name,"group":json.loads(x.config_json),"is_active":x.is_active}

@router.get("/fnb/pos-rules")
def list_rules(db:Session=Depends(get_db),_:User=Depends(require_permission("items.read"))):
    return {
        "pricing_rules":[rule_out(x) for x in db.scalars(select(PosPricingRule).order_by(PosPricingRule.name)).all()],
        "modifier_templates":[modifier_out(x) for x in db.scalars(select(PosModifierTemplate).order_by(PosModifierTemplate.name)).all()],
    }

@router.post("/fnb/pos-rules/pricing",status_code=201)
def create_rule(payload:PricingRuleIn,db:Session=Depends(get_db),user:User=Depends(require_permission("items.*"))):
    row=PosPricingRule(name=payload.name.strip(),qualifier_tag=payload.qualifier_tag,target_tag=payload.target_tag,is_active=payload.is_active)
    db.add(row);db.flush();add_audit(db,actor_user_id=user.id,action="pos.pricing_rule_created",entity_type="pos_pricing_rule",entity_id=row.id,details=rule_out(row));db.commit();return rule_out(row)

@router.put("/fnb/pos-rules/pricing/{rule_id}")
def update_rule(rule_id:str,payload:PricingRuleIn,db:Session=Depends(get_db),user:User=Depends(require_permission("items.*"))):
    row=db.get(PosPricingRule,rule_id)
    if not row: raise HTTPException(404,"Pricing rule not found")
    row.name=payload.name.strip();row.qualifier_tag=payload.qualifier_tag;row.target_tag=payload.target_tag;row.is_active=payload.is_active
    add_audit(db,actor_user_id=user.id,action="pos.pricing_rule_updated",entity_type="pos_pricing_rule",entity_id=row.id,details=rule_out(row));db.commit();return rule_out(row)

@router.post("/fnb/pos-rules/modifiers",status_code=201)
def create_modifier(payload:ModifierTemplateIn,db:Session=Depends(get_db),user:User=Depends(require_permission("items.*"))):
    row=PosModifierTemplate(name=payload.name.strip(),config_json=json.dumps(payload.group),is_active=payload.is_active)
    db.add(row);db.flush();add_audit(db,actor_user_id=user.id,action="pos.modifier_template_created",entity_type="pos_modifier_template",entity_id=row.id,details={"name":row.name});db.commit();return modifier_out(row)

@router.put("/fnb/pos-rules/modifiers/{template_id}")
def update_modifier(template_id:str,payload:ModifierTemplateIn,db:Session=Depends(get_db),user:User=Depends(require_permission("items.*"))):
    row=db.get(PosModifierTemplate,template_id)
    if not row: raise HTTPException(404,"Modifier template not found")
    row.name=payload.name.strip();row.config_json=json.dumps(payload.group);row.is_active=payload.is_active
    add_audit(db,actor_user_id=user.id,action="pos.modifier_template_updated",entity_type="pos_modifier_template",entity_id=row.id,details={"name":row.name});db.commit();return modifier_out(row)
