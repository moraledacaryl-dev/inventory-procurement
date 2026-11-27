/** Execute the actual frontend API module with controlled environment/transport. */
import assert from "node:assert/strict";
import fs from "node:fs";
import {createRequire} from "node:module";
import path from "node:path";
import vm from "node:vm";
const root=path.resolve(import.meta.dirname,"..");
const require=createRequire(path.join(root,"frontend/package.json"));
const ts=require("typescript");
const code=ts.transpileModule(fs.readFileSync(path.join(root,"frontend/lib/api.ts"),"utf8"),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
function load(env,calls=[]){
  const exports={};
  const context={exports,process:{env},Headers,fetch:async(url,init)=>{calls.push({url,init});return new Response(JSON.stringify({ok:true}),{headers:{"Content-Type":"application/json","x-inventory-environment":"isolated-training"}})},require:()=>({trainingAttempt:()=>null,forgetTrainingAttempt:()=>{}})};
  vm.runInNewContext(code,context,{filename:"actual-frontend-api.js"});
  return {exports,calls};
}
for(const address of ["https://inventory.hiddenoasis.app/api/v1","https://unrelated.invalid/api","http://127.0.0.1:9999/api"]){
  // Module loading itself must refuse, so direct consumers of exported API
  // cannot initiate a blob/download request before the normal api() check.
  const calls=[];
  assert.throws(()=>load({NEXT_PUBLIC_INVENTORY_TRAINING:"1",NEXT_PUBLIC_API_URL:address},calls),/Training cannot use an external API address/);
  assert.equal(calls.length,0);
}
const training=load({NEXT_PUBLIC_INVENTORY_TRAINING:"1"});
assert.equal(training.exports.API,"/api/v1");assert.equal((await training.exports.api("/health")).ok,true);
assert.equal(training.calls.length,1);assert.equal(training.calls[0].url,"/api/v1/health");
const operational=load({NEXT_PUBLIC_API_URL:"https://inventory.hiddenoasis.app/api/v1"});
assert.equal(operational.exports.API,"https://inventory.hiddenoasis.app/api/v1");assert.equal(operational.calls.length,0);
console.log("Frontend training configuration refuses every nonlocal API before transport; the relative proxy and operational configuration remain valid.");
