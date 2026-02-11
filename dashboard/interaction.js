// dashboard/interaction.js — graph↔feed linking, popups, hover
var _hlTimer=null;
const _HL_MS=3000,_FLASH_MS=2000,_POP_MW=310;
const _T='<span translate="no">',_TC='</span>';

/** Highlight edge by source→destination, auto-reset after 3s */
function highlightEdge(cy,source,destination){
  if(_hlTimer)clearTimeout(_hlTimer);
  cy.edges('.highlight').stop().style({opacity:1}).removeClass('highlight');
  const e=cy.getElementById(source+'->'+destination);
  if(!e.length)return;
  e.addClass('highlight');
  cy.animate({center:{eles:e},duration:300});
  function doPulse(){e.animate({style:{opacity:0.4}},{duration:400,complete:function(){
    e.animate({style:{opacity:1}},{duration:400,complete:function(){if(e.hasClass('highlight'))doPulse()}})}})}
  doPulse();
  _hlTimer=setTimeout(()=>{e.stop().style({opacity:1});e.removeClass('highlight');_hlTimer=null},_HL_MS);
}

/** Color edges by highest severity drift event — classes only */
function colorEdgesBySeverity(cy,events){
  cy.edges().removeClass('drift-critical drift-high drift-medium drift-low');
  const sevMap={};
  events.forEach(ev=>{
    const eid=ev.source+'->'+ev.destination,prev=sevMap[eid];
    if(!prev||_sevRank(ev.severity)>_sevRank(prev))sevMap[eid]=ev.severity;
  });
  Object.entries(sevMap).forEach(([eid,sev])=>{
    const e=cy.getElementById(eid);
    if(e.length)e.addClass('drift-'+sev);
  });
}

/** Sync drift feed hover with graph — mouseenter/mouseleave only */
function syncDriftFeedWithGraph(cy,events){
  document.querySelectorAll('.card[data-src][data-dst]').forEach(card=>{
    if(card._synced)return;card._synced=true;
    const edge=cy.getElementById(card.dataset.src+'->'+card.dataset.dst);
    card.addEventListener('mouseenter',()=>{if(edge.length)edge.addClass('hover-bright')});
    card.addEventListener('mouseleave',()=>{if(edge.length)edge.removeClass('hover-bright')});
  });
}

/** Scroll to feed card by index, flash it, highlight its edge */
function _scrollToCard(idx){
  const card=document.querySelector('.card[data-idx="'+idx+'"]');
  if(!card)return;
  card.scrollIntoView({behavior:'smooth',block:'center'});
  document.querySelectorAll('.card.open').forEach(c=>c.classList.remove('open'));
  card.classList.add('open','flash');
  setTimeout(()=>card.classList.remove('flash'),_FLASH_MS);
  highlightEdge(cy,card.dataset.src,card.dataset.dst);
}

function _sevRank(s){return{critical:4,high:3,medium:2,low:1}[s]||0}
function _driftEdge(s,d){return driftData.filter(e=>e.source===s&&e.destination===d)}
function _driftNode(n){return driftData.filter(e=>e.source===n||e.destination===n||(e.affected&&e.affected.includes(n)))}

/** Generate drift event links HTML with data-scroll-idx */
function _dLinks(evts){
  if(!evts.length)return'';
  let h='<div style="margin-top:6px">\u26A0 '+evts.length+' drift-\u0441\u043E\u0431\u044B\u0442\u0438\u0439</div>';
  evts.forEach(ev=>{
    h+='<span class="p-link" data-scroll-idx="'+driftData.indexOf(ev)+'">'+ev.title+'</span><br>';
  });return h;
}

/** Generate a popup row with translate="no" on value */
function _pRow(lbl,val,cls){return '<div class="p-row'+(cls||'')+'">'+lbl+': '+_T+val+_TC+'</div>'}

/** Build node popup HTML */
function _nodeHTML(nm,ns,nt,out,inp,rel){
  let h='<b>'+_T+nm+_TC+'</b>'+_pRow('Type',nt)+_pRow('Namespace',ns);
  if(out.length){h+='<div class="p-row"><b>\u0418\u0441\u0445\u043E\u0434\u044F\u0449\u0438\u0435:</b></div>';
    out.forEach(e=>{h+='<div class="p-row">\u2192 '+_T+e.destination+_TC+' ('+e.request_count+' req, '+(e.error_rate*100).toFixed(1)+'% err)</div>'})}
  if(inp.length){h+='<div class="p-row"><b>\u0412\u0445\u043E\u0434\u044F\u0449\u0438\u0435:</b></div>';
    inp.forEach(e=>{h+='<div class="p-row">\u2190 '+_T+e.source+_TC+' ('+e.request_count+' req, '+(e.error_rate*100).toFixed(1)+'% err)</div>'})}
  return h+_dLinks(rel);
}

/** Build edge popup HTML */
function _edgeHTML(d,evts){
  var er=(d.error_rate*100).toFixed(1);
  let h='<b>'+_T+d.source+' \u2192 '+d.target+_TC+'</b>';
  h+=_pRow('Requests',d.request_count);
  h+=_pRow('Error rate',er+'%',d.error_rate>0.05?' red':'');
  h+=_pRow('Avg latency',d.avg_latency_ms.toFixed(1)+' ms');
  h+=_pRow('P99 latency',d.p99_latency_ms.toFixed(1)+' ms',d.p99_latency_ms>100?' red':'');
  evts.forEach(ev=>{h+='<div style="margin-top:4px"><span class="badge badge-'+ev.severity+'">'+ev.severity+'</span></div>'});
  return h+_dLinks(evts);
}

/** Init popups, hover effects, event delegation — call once after cy ready */
function initInteractions(){
  const popup=document.getElementById('popup'),cyCont=document.getElementById('cy');
  function hide(){popup.style.display='none'}
  function show(html,pos){
    popup.innerHTML=html;popup.style.display='block';
    const rw=cyCont.clientWidth,rh=cyCont.clientHeight;
    let l=pos.x+15,t=pos.y-10;
    if(l+_POP_MW>rw)l=pos.x-_POP_MW-5;if(l<0)l=5;
    if(t+popup.offsetHeight>rh)t=rh-popup.offsetHeight-5;if(t<0)t=5;
    popup.style.left=l+'px';popup.style.top=t+'px';
  }
  popup.addEventListener('mousedown',e=>e.stopPropagation());
  popup.addEventListener('pointerdown',e=>e.stopPropagation());
  popup.addEventListener('click',function(e){
    const link=e.target.closest('.p-link[data-scroll-idx]');
    if(link){e.stopPropagation();_scrollToCard(parseInt(link.dataset.scrollIdx))}
  });
  // Node click popup
  cy.on('tap','node',function(evt){
    const n=evt.target,nm=n.data('name'),ns=n.data('namespace')||'default',nt=n.data('node_type');
    const out=graphData.edges.filter(e=>e.source===nm),inp=graphData.edges.filter(e=>e.destination===nm);
    const rel=_driftNode(nm);
    show(_nodeHTML(nm,ns,nt,out,inp,rel),n.renderedPosition());
    document.querySelectorAll('.card.flash').forEach(c=>c.classList.remove('flash'));
    rel.forEach(ev=>{const card=document.querySelector('.card[data-idx="'+driftData.indexOf(ev)+'"]');
      if(card){card.classList.add('flash');setTimeout(()=>card.classList.remove('flash'),_FLASH_MS)}});
  });
  // Edge click popup
  cy.on('tap','edge',function(evt){
    const e=evt.target,d=e.data(),evts=_driftEdge(d.source,d.target);
    show(_edgeHTML(d,evts),e.renderedMidpoint());
    if(evts.length)_scrollToCard(driftData.indexOf(evts[0]));
  });
  // Close popup
  cy.on('tap',function(evt){if(evt.target===cy)hide()});
  document.addEventListener('keydown',function(evt){if(evt.key==='Escape')hide()});
  // Hover: node
  cy.on('mouseover','node',function(evt){
    const n=evt.target;n.addClass('hover');n.connectedEdges().addClass('hover-bright');
    n.neighborhood('node').addClass('hover-conn');cyCont.style.cursor='pointer';
  });
  cy.on('mouseout','node',function(evt){
    const n=evt.target;n.removeClass('hover');n.connectedEdges().removeClass('hover-bright');
    n.neighborhood('node').removeClass('hover-conn');cyCont.style.cursor='default';
  });
  // Hover: edge
  cy.on('mouseover','edge',function(evt){
    const e=evt.target;e.addClass('hover-bright');
    e.source().addClass('hover-conn');e.target().addClass('hover-conn');cyCont.style.cursor='pointer';
  });
  cy.on('mouseout','edge',function(evt){
    const e=evt.target;e.removeClass('hover-bright');
    e.source().removeClass('hover-conn');e.target().removeClass('hover-conn');cyCont.style.cursor='default';
  });
}
