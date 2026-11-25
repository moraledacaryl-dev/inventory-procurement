/** Bind each tab to the practice it actually loaded, independent of other tabs. */
const key="inventory-training-attempt";
let boundAttempt:string|null=null;

export function trainingAttempt() {
  if(typeof window==="undefined")return null;
  if(boundAttempt)return boundAttempt;
  try { boundAttempt=sessionStorage.getItem(key); } catch { /* Storage may be disabled. */ }
  if(!boundAttempt)try { boundAttempt=localStorage.getItem(key); } catch { /* No resumable identity. */ }
  if(boundAttempt&&!/^[a-f0-9-]{36}$/.test(boundAttempt))boundAttempt=null;
  if(boundAttempt)try { sessionStorage.setItem(key,boundAttempt); } catch { /* The in-memory binding still protects this page. */ }
  return boundAttempt;
}

export function rememberTrainingAttempt(attempt:string) {
  boundAttempt=attempt;
  try { sessionStorage.setItem(key,attempt); } catch { /* Preserve the tab binding in memory. */ }
  try { localStorage.setItem(key,attempt); } catch { /* The active tab can still finish. */ }
}

export function forgetTrainingAttempt() {
  boundAttempt=null;
  try { sessionStorage.removeItem(key); } catch { /* No stored tab binding. */ }
}
