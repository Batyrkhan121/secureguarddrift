// dashboard/policies.js
// PolicyPanel для отображения NetworkPolicy предложений

async function loadPolicies(status='pending'){
  try{
    const resp=await fetch(`/api/policies?status=${status}`);
    const data=await resp.json();
    return data.policies||[];
  }catch(err){
    console.error('Failed to load policies:',err);
    return[];
  }
}

function renderPolicies(policies){
  const feed=document.getElementById('policy-feed');
  if(!policies.length){
    feed.innerHTML='<div style="text-align:center;padding:40px;color:var(--muted)">No policy suggestions</div>';
    return;
  }

  feed.innerHTML=policies.map(p=>`
    <div class="policy-card sev-${p.severity}" data-id="${p.policy_id}">
      <div class="policy-head">
        <span class="policy-title">${p.policy_id}</span>
        <span class="badge badge-${p.severity}">${p.risk_score}</span>
      </div>
      <div class="policy-meta">
        <span>${p.source} → ${p.destination}</span>
        <span class="policy-status status-${p.status}">${p.status}</span>
      </div>
      <div class="policy-reason">${p.reason}</div>
      <div class="policy-actions">
        <button class="btn-small btn-download" onclick="downloadPolicy('${p.policy_id}')">
          Download YAML
        </button>
        ${p.status==='pending'?`
          <button class="btn-small btn-approve" onclick="approvePolicy('${p.policy_id}')">
            Approve
          </button>
          <button class="btn-small btn-reject" onclick="rejectPolicy('${p.policy_id}')">
            Reject
          </button>
        `:''}
      </div>
    </div>
  `).join('');
}

async function downloadPolicy(policyId){
  window.location=`/api/policies/${policyId}/yaml`;
}

async function downloadBundle(){
  window.location='/api/policies/bundle/download?status=pending';
}

async function approvePolicy(policyId){
  try{
    await fetch(`/api/policies/${policyId}/approve`,{method:'POST'});
    refreshPolicies();
  }catch(err){
    console.error('Failed to approve policy:',err);
    alert('Failed to approve policy');
  }
}

async function rejectPolicy(policyId){
  try{
    await fetch(`/api/policies/${policyId}/reject`,{method:'POST'});
    refreshPolicies();
  }catch(err){
    console.error('Failed to reject policy:',err);
    alert('Failed to reject policy');
  }
}

async function refreshPolicies(){
  const status=document.getElementById('sel-policy-status').value;
  const policies=await loadPolicies(status);
  renderPolicies(policies);
  updatePolicySummary(policies);
}

function updatePolicySummary(policies){
  const pending=policies.filter(p=>p.status==='pending').length;
  const summary=document.getElementById('summary');
  const current=summary.innerHTML;
  if(pending>0&&!current.includes('policies suggested')){
    summary.innerHTML+=` <span>|</span> <span style="color:var(--high)">${pending} policies suggested</span>`;
  }
}

async function initPolicies(){
  const policies=await loadPolicies('pending');
  renderPolicies(policies);
  updatePolicySummary(policies);
}
