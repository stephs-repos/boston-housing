const PLACES={'02108':'Beacon Hill','02109':'Waterfront','02110':'Financial District','02111':'Chinatown','02113':'North End','02114':'West End','02115':'Fenway','02116':'Back Bay','02118':'South End','02119':'Roxbury','02120':'Mission Hill','02121':'Dorchester · Grove Hall','02122':'Dorchester · Neponset','02124':'Dorchester · Codman Sq','02125':'Dorchester · Savin Hill','02126':'Mattapan','02127':'South Boston','02128':'East Boston','02129':'Charlestown','02130':'Jamaica Plain','02131':'Roslindale','02132':'West Roxbury','02134':'Allston','02135':'Brighton','02136':'Hyde Park','02163':'Allston · HBS','02199':'Prudential','02203':'Government Center','02210':'Seaport','02215':'Kenmore','02138':'Cambridge · Harvard Sq','02139':'Cambridge · Central Sq','02140':'Cambridge · Porter','02141':'Cambridge · East','02142':'Cambridge · Kendall','02143':'Somerville · Union Sq','02144':'Somerville · Davis Sq','02145':'Somerville · Winter Hill'};
// All rents are stored in US dollars; C$ converts at the Bank of Canada rate fetched at build time (DATA.fx).
const fxRate=()=>S.cur==='CAD'?DATA.fx.rate:1;
const money=v=>v==null?'—':(S.cur==='CAD'?'C$':'US$')+d3.format(',')(Math.round(v*fxRate()));
const num1=v=>v==null?'—':(v>=10?Math.round(v):v.toFixed(1));
const pct=v=>v==null?'—':v+'%';
const UNITS={room:'room in a 3‑bed share',b0:'studio',b1:'1‑bedroom'};
const LAYERS=[
 {id:'fit',group:'Overall',label:'Best fit (adjustable)',f:v=>v==null?'—':Math.round(v),dir:1,best:'best fit first'},
 {id:'rent',group:'Cost',label:'Rent',f:money,dir:-1,best:'cheapest first'},
 {id:'zori',group:'Cost',label:'Zillow typical asking rent, all sizes',f:money,dir:-1,best:'cheapest first'},
 {id:'commute',group:'Getting to school',label:'Commute to school (minutes)',f:v=>v==null?'—':v+' min',dir:-1,best:'shortest first'},
 {id:'viol',group:'Reported crime, {{FBI_YEAR}}',label:'Violent crime per 1,000 residents',f:num1,dir:-1,best:'lowest first'},
 {id:'prop',group:'Reported crime, {{FBI_YEAR}}',label:'Property crime per 1,000 residents',f:num1,dir:-1,best:'lowest first'},
 {id:'music',group:'Within a 12‑minute walk',label:'Music venues, theatres, clubs',f:num1,dir:1,best:'most first'},
 {id:'bars',group:'Within a 12‑minute walk',label:'Bars and pubs',f:num1,dir:1,best:'most first'},
 {id:'cafes',group:'Within a 12‑minute walk',label:'Cafés',f:num1,dir:1,best:'most first'},
 {id:'grocery',group:'Within a 12‑minute walk',label:'Grocery stores',f:num1,dir:1,best:'most first'},
 {id:'parks',group:'Within a 12‑minute walk',label:'Parks',f:num1,dir:1,best:'most first'},
 {id:'bikes',group:'Within a 12‑minute walk',label:'Bluebikes stations',f:num1,dir:1,best:'most first'},
 {id:'young',group:'Who lives there',label:'Residents aged 20–34',f:pct,dir:1,best:'highest first'},
 {id:'carfree',group:'Who lives there',label:'Workers who commute without a car',f:pct,dir:1,best:'highest first'},
 {id:'renters',group:'Who lives there',label:'Households that rent',f:pct,dir:1,best:'highest first'},
];
const L=Object.fromEntries(LAYERS.map(l=>[l.id,l]));
const FACTORS=[
 {id:'rent',label:'Low rent',w:3,dir:-1,get:p=>rentOf(p)},
 {id:'commute',label:'Short commute',w:2,dir:-1,get:p=>p.commute},
 {id:'safety',label:'Low violent crime',w:2,dir:-1,get:p=>p.viol},
 {id:'night',label:'Music and nightlife',w:1,dir:1,get:p=>p.music+p.bars},
 {id:'daily',label:'Cafés and groceries',w:1,dir:1,get:p=>p.cafes+p.grocery},
 {id:'young',label:'People his age',w:1,dir:1,get:p=>p.young},
];
const RAMP=[1,2,3,4,5,6,7].map(i=>`var(--r${i})`);
const MI=1.609344;
const S={layer:'fit',unit:'room',basis:'zillow',cur:'USD',budget:1500,radius:7,showT:true,hot:null};
const zips=DATA.zips.features;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
const placeName=p=>PLACES[p.zip]||p.city||`ZIP ${p.zip}`;
const shortName=p=>(PLACES[p.zip]||p.city||'').replace(/^.* · /,'');
const hav=(a,b)=>{const r=Math.PI/180,dl=(b[1]-a[1])*r,dn=(b[0]-a[0])*r,h=Math.sin(dl/2)**2+Math.cos(a[1]*r)*Math.cos(b[1]*r)*Math.sin(dn/2)**2;return 6371*2*Math.asin(Math.sqrt(h))};
zips.forEach(f=>{const p=f.properties;p.c=d3.geoCentroid(f);p.mi=p.km/MI;
  let best=null;for(const s of DATA.stations){const d=hav(p.c,[s[1],s[2]]);if(!best||d<best[1])best=[s[0],d]}
  p.stn=best[0];p.stnMi=best[1]/MI;});

const box=document.getElementById('mapbox'),svg=d3.select('#map'),tip=document.getElementById('tip');
const W=1000,H=1000;svg.attr('viewBox',`0 0 ${W} ${H}`);
const proj=d3.geoMercator().fitExtent([[10,10],[W-10,H-10]],DATA.zips),path=d3.geoPath(proj);
svg.append('defs').html('<pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="var(--over)"/><line x1="0" y1="0" x2="0" y2="6" stroke="var(--muted)" stroke-width="1.2"/></pattern>');
const g=svg.append('g');
const zipSel=g.append('g').selectAll('path').data(zips).join('path').attr('class','zip').attr('d',path);

// distance rings: 1.5 mi ≈ 30 min walk
const school=DATA.school,sp=proj(school);
const ringG=g.append('g');
[1.5,4,7].forEach(mi=>{const c=d3.geoCircle().center(school).radius(mi*MI/111.2)();
  ringG.append('path').attr('class','ring').attr('d',path(c));
  const top=proj([school[0],school[1]+mi*MI/111.2]);
  ringG.append('text').attr('class','ringlbl').attr('x',top[0]+4).attr('y',top[1]+11).text(`${mi} mi`)});

const tG=g.append('g');
tG.selectAll('path').data(DATA.lines).join('path').attr('class','tline').attr('stroke',d=>d.color).attr('d',d=>path({type:'LineString',coordinates:d.pts}));
const stnSel=tG.selectAll('circle').data(DATA.stations).join('circle').attr('class','stn').attr('cx',d=>proj([d[1],d[2]])[0]).attr('cy',d=>proj([d[1],d[2]])[1]);

// one label per place, at its largest ZIP
const byPlace=new Map();zips.forEach(f=>{const n=shortName(f.properties);if(!n)return;const a=path.area(f);if(!byPlace.has(n)||byPlace.get(n).a<a)byPlace.set(n,{f,a,n})});
const labels=[...byPlace.values()];
const lblSel=g.append('g').selectAll('text').data(labels).join('text').attr('class','town').attr('text-anchor','middle')
  .attr('x',d=>path.centroid(d.f)[0]).attr('y',d=>path.centroid(d.f)[1]).text(d=>d.n);
const schoolG=g.append('g').attr('transform',`translate(${sp})`).style('pointer-events','none');
schoolG.append('circle').attr('r',7).attr('fill','var(--school)').attr('stroke','var(--bg)').attr('stroke-width',2.5);
schoolG.append('text').attr('class','town').attr('x',11).attr('y',4).attr('text-anchor','start').style('font-size','12px').text('North Bennet St School');

let K=1;
const zoom=d3.zoom().scaleExtent([1,14]).translateExtent([[0,0],[W,H]]).on('zoom',e=>{K=e.transform.k;g.attr('transform',e.transform);sizeMarks();hideTip()});
svg.call(zoom);
function sizeMarks(){
  lblSel.style('font-size',`${10/K}px`).style('stroke-width',`${3/K}px`).attr('display',d=>d.a*K*K>(d.n.length*d.n.length*22)?null:'none');
  stnSel.attr('r',2.6/Math.sqrt(K)).attr('display',K<2.2?'none':null);
  schoolG.attr('transform',`translate(${sp}) scale(${1/K})`);
  ringG.selectAll('text').style('font-size',`${10/K}px`);
}
document.getElementById('zin').onclick=()=>svg.transition().duration(250).call(zoom.scaleBy,1.6);
document.getElementById('zout').onclick=()=>svg.transition().duration(250).call(zoom.scaleBy,1/1.6);
document.getElementById('zreset').onclick=()=>svg.transition().duration(300).call(zoom.transform,d3.zoomIdentity);
// open zoomed on the core so the school's neighbourhood is readable
svg.call(zoom.transform,d3.zoomIdentity.translate(W/2,H/2).scale(2.4).translate(-sp[0],-sp[1]));

// HUD gives rent per bedroom count but sits near the 40th percentile and repeats one value across several ZIPs.
// Zillow tracks asking rents per ZIP but only for all unit sizes together. Rescale HUD's figure for the chosen
// unit by how far Zillow's typical rent sits from HUD priced over the ZIP's own mix of rental units (hudMix).
const zillowRatio=p=>p.zori&&p.hudMix?p.zori/p.hudMix:null;
const BASES={zillow:'Asking (Zillow-adjusted)',blend:'Blend',hud:'HUD benchmark'};
function rentOf(p,basis=S.basis){
  const h=p[S.unit],r=zillowRatio(p);
  if(h==null)return null;
  if(basis==='hud'||r==null)return h;  // no Zillow index for this ZIP: HUD is all there is
  return basis==='zillow'?h*r:h*(1+r)/2;
}
const val=(p,id)=>id==='rent'?rentOf(p):p[id];
function computeFit(){
  const ranks=FACTORS.map(fc=>{const v=zips.map(f=>fc.get(f.properties)).filter(x=>x!=null).sort((a,b)=>a-b);
    return p=>{const x=fc.get(p);if(x==null)return null;const lo=d3.bisectLeft(v,x),hi=d3.bisectRight(v,x);const r=((lo+hi-1)/2)/(v.length-1);return fc.dir>0?r:1-r}});
  zips.forEach(f=>{if(f.properties.pop<500){f.properties.fit=null;return}let s=0,w=0;FACTORS.forEach((fc,i)=>{const r=ranks[i](f.properties);if(r!=null&&fc.w>0){s+=fc.w*r;w+=fc.w}});f.properties.fit=w?100*s/w:null});
}
let scale,edges;
const over=p=>rentOf(p)!=null&&rentOf(p)>S.budget;
function render(){
  computeFit();
  const id=S.layer,vals=zips.map(f=>val(f.properties,id)).filter(v=>v!=null).sort((a,b)=>a-b);
  const qs=[...new Set([1,2,3,4,5,6].map(i=>d3.quantile(vals,i/7)))].filter(q=>q>vals[0]);
  const cols=qs.length+1,ramp=d3.range(cols).map(i=>RAMP[Math.round(i*(RAMP.length-1)/Math.max(1,cols-1))]);
  scale=d3.scaleThreshold().domain(qs).range(ramp);edges=[vals[0],...qs];
  zipSel.classed('nodata',f=>val(f.properties,id)==null)
    .attr('fill',f=>{const v=val(f.properties,id);if(v==null)return null;return over(f.properties)?'var(--over)':scale(v)});
  tG.attr('display',S.showT?null:'none');
  document.getElementById('fitPanel').hidden=id!=='fit';
  drawLegend();drawRank();
}
const BASIS_SHORT={zillow:'asking',blend:'blend',hud:'HUD'};
const layerTitle=id=>id==='rent'?`Rent, ${UNITS[S.unit]}, ${BASIS_SHORT[S.basis]}`:L[id].label;
function drawLegend(){
  const l=L[S.layer],fmtE=v=>S.layer==='rent'||S.layer==='zori'?d3.format(',')(Math.round(v*fxRate()/50)*50):l.f(v);
  document.getElementById('legend').innerHTML=`<div class="t">${layerTitle(S.layer)} · ${S.layer==='rent'||S.layer==='zori'?(S.cur==='CAD'?'C$ ':'US$ '):''}from</div>
   <div class="sw">${scale.range().map((c,i)=>`<div><i style="background:${c}"></i><b>${fmtE(edges[i])}</b></div>`).join('')}</div>
   <div class="k"><span><i style="background:var(--over)"></i>${UNITS[S.unit]} over ${money(S.budget)}</span><span><i class="h"></i>No data</span></div>`;
}
function drawRank(){
  const id=S.layer,l=L[id],list=zips.map(f=>f.properties).filter(p=>p.mi<=S.radius&&val(p,id)!=null).sort((a,b)=>-l.dir*(val(a,id)-val(b,id)));
  const under=list.filter(p=>!over(p)).length;
  document.getElementById('rankTitle').textContent=`${layerTitle(id)}, ${l.best}`;
  document.getElementById('rankSub').textContent=`${list.length} ZIPs within ${S.radius} mi · ${under} with a ${UNITS[S.unit]} at or under ${money(S.budget)}`;
  document.getElementById('rank').innerHTML=list.map((p,i)=>`<li data-z="${esc(p.zip)}" style="${over(p)?'opacity:.5':''}">
    <span class="n">${String(i+1).padStart(2,'0')}</span><span class="nm">${esc(placeName(p))} <span style="color:var(--muted);font-weight:400">${esc(p.zip)}</span></span><span class="p">${l.f(val(p,id))}</span>
    <span class="meta">${money(rentOf(p))} ${UNITS[S.unit]} · ${p.commute} min to school · ${esc(p.stn)} ${p.stnMi.toFixed(1)} mi</span></li>`).join('');
}
function tipHtml(p){
  const row=(id,label)=>`<div class="row ${id===S.layer?'on':''}"><span>${label||L[id].label}</span><span>${L[id].f(val(p,id))}</span></div>`;
  const crimeNote=p.crimeNote?`<div class="sub">Crime: not shown (${esc(p.crimeNote)})</div>`:p.crimeSrc==='town'?`<div class="sub">Crime rate is for all of ${esc(p.town)}</div>`:'';
  return `<h3>${esc(placeName(p))} · ${esc(p.zip)}</h3><div class="sub">${p.mi.toFixed(1)} mi from school · nearest T: ${esc(p.stn)} (${p.stnMi.toFixed(1)} mi)</div>
   ${row('fit','Best-fit score')}
   <div class="grp">Cost, ${UNITS[S.unit]}</div>
   ${Object.entries(BASES).map(([b,label])=>`<div class="row ${S.layer==='rent'&&b===S.basis?'on':''}"><span>${label}</span><span>${money(rentOf(p,b))}</span></div>`).join('')}
   ${zillowRatio(p)==null?'<div class="sub">No Zillow index here, so all three use HUD</div>':`<div class="sub">Zillow runs ${Math.round(Math.abs(zillowRatio(p)-1)*100)}% ${zillowRatio(p)>=1?'above':'below'} HUD in this ZIP</div>`}
   ${row('zori','Zillow typical, all sizes')}
   ${p.yoy!=null?`<div class="sub">Zillow change over 12 months: ${p.yoy>0?'+':''}${p.yoy}%</div>`:''}
   <div class="grp">School</div>${row('commute','Commute, walk + T or bus')}
   <div class="grp">Reported crime per 1,000 residents</div>${row('viol','Violent')}${row('prop','Property')}${crimeNote}
   <div class="grp">Within a 12‑minute walk</div>${row('music','Music venues, theatres, clubs')}${row('bars')}${row('cafes')}${row('grocery')}${row('parks')}${row('bikes')}
   <div class="grp">Who lives there</div>${row('young','Aged 20–34')}${row('carfree','Commute without a car')}${row('renters')}`;
}
function showTip(p,x,y){
  tip.innerHTML=tipHtml(p);tip.hidden=false;const bw=box.clientWidth,bh=box.clientHeight,tw=tip.offsetWidth,th=tip.offsetHeight;
  tip.style.left=(x+14+tw>bw-8?Math.max(8,x-14-tw):x+14)+'px';tip.style.top=Math.min(Math.max(8,y-th/2),bh-th-8)+'px';
}
function hideTip(){tip.hidden=true}
function setHot(z){S.hot=z;zipSel.classed('hot',f=>f.properties.zip===z).filter('.hot').raise();
  document.querySelectorAll('#rank li').forEach(li=>li.classList.toggle('hot',li.dataset.z===z))}
zipSel.on('pointermove',(e,f)=>{const [x,y]=d3.pointer(e,box);showTip(f.properties,x,y);setHot(f.properties.zip)})
  .on('pointerleave',()=>{hideTip();setHot(null)});
document.getElementById('rank').addEventListener('click',e=>{const li=e.target.closest('li');if(!li)return;
  const f=zips.find(f=>f.properties.zip===li.dataset.z),c=path.centroid(f),k=Math.max(K,4);
  setHot(f.properties.zip);
  svg.transition().duration(400).call(zoom.transform,d3.zoomIdentity.translate(W/2,H/2).scale(k).translate(-c[0],-c[1]))
   .on('end',()=>{const r=svg.node().getBoundingClientRect(),b=box.getBoundingClientRect(),s=r.width/W;showTip(f.properties,(W/2)*s+(r.left-b.left),(H/2)*s+(r.top-b.top))});
});
const layerSel=document.getElementById('layer');
d3.groups(LAYERS,l=>l.group).forEach(([g,ls])=>{const og=document.createElement('optgroup');og.label=g;
  ls.forEach(l=>{const o=document.createElement('option');o.value=l.id;o.textContent=l.label;og.append(o)});layerSel.append(og)});
layerSel.value=S.layer;layerSel.onchange=()=>{S.layer=layerSel.value;render()};
document.getElementById('weights').innerHTML=FACTORS.map(fc=>`<label for="w-${fc.id}">${fc.label} <span class="val" id="wv-${fc.id}">${fc.w}</span><input type="range" id="w-${fc.id}" min="0" max="3" step="1" value="${fc.w}"></label>`).join('');
FACTORS.forEach(fc=>{const el=document.getElementById('w-'+fc.id);el.oninput=()=>{fc.w=+el.value;document.getElementById('wv-'+fc.id).textContent=fc.w;render()}});
document.querySelectorAll('#unit button').forEach(b=>b.onclick=()=>{S.unit=b.dataset.m;
  document.querySelectorAll('#unit button').forEach(x=>x.setAttribute('aria-pressed',x===b));render()});
document.querySelectorAll('#basis button').forEach(b=>b.onclick=()=>{S.basis=b.dataset.b;
  document.querySelectorAll('#basis button').forEach(x=>x.setAttribute('aria-pressed',x===b));render()});
const bud=document.getElementById('budget');
bud.oninput=()=>{S.budget=+bud.value/fxRate();document.getElementById('budgetVal').textContent=money(S.budget);render()};
// The slider works in the shown currency; S.budget stays in US dollars.
function syncBudget(){const k=fxRate(),r=v=>Math.round(v*k/50)*50;bud.min=r(800);bud.max=r(4500);bud.value=r(S.budget);S.budget=+bud.value/k;
  document.getElementById('budgetVal').textContent=money(S.budget)}
document.querySelectorAll('#cur button').forEach(b=>b.onclick=()=>{S.cur=b.dataset.c;
  document.querySelectorAll('#cur button').forEach(x=>x.setAttribute('aria-pressed',x===b));syncBudget();render()});
document.getElementById('fxNote').textContent=`US$1 = C$${DATA.fx.rate.toFixed(4)}, ${DATA.fx.source} rate for ${d3.timeFormat('%B %-d, %Y')(new Date(DATA.fx.date+'T12:00'))}`;
syncBudget();
document.getElementById('radius').onchange=e=>{S.radius=+e.target.value;drawRank()};
document.getElementById('showT').onchange=e=>{S.showT=e.target.checked;render()};
document.getElementById('asof').textContent=d3.timeFormat('%B %Y')(new Date(DATA.asof+'T12:00'));
sizeMarks();render();
