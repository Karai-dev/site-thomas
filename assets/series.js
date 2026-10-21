(function(){
var rail=document.getElementById('rail'),
    slides=[].slice.call(rail.querySelectorAll('.slide')),
    num=document.getElementById('c-n'),bar=document.getElementById('c-b'),
    lb=document.getElementById('lb'),lbi=document.getElementById('lb-i'),lbc=document.getElementById('lb-c'),
    cur=0,target=null,raf=null;
function mobile(){return matchMedia('(max-width:820px)').matches}
function pad(n){return ('0'+n).slice(-2)}
function upd(){
  var n=1,lim=window.innerWidth*.45;
  slides.forEach(function(e,i){if(e.getBoundingClientRect().left<lim)n=i+1});
  num.textContent=pad(n);
  var m=rail.scrollWidth-rail.clientWidth;bar.style.width=(m>0?rail.scrollLeft/m*100:100)+'%';
}
rail.addEventListener('scroll',function(){if(!raf)target=null;upd()});
window.addEventListener('resize',upd);upd();

/* Défilement fluide à la molette / au trackpad : le texte sort de l'écran avec le rail */
function tick(){
  var d=target-rail.scrollLeft;
  if(Math.abs(d)<.5){rail.scrollLeft=target;raf=null;target=null;return}
  var st=d*.12;if(Math.abs(st)<1)st=d>0?1:-1;
  rail.scrollLeft+=st;raf=requestAnimationFrame(tick);
}
rail.addEventListener('wheel',function(e){
  if(mobile())return;
  var p=e.target.closest&&e.target.closest('.panel');
  if(p&&Math.abs(e.deltaY)>=Math.abs(e.deltaX)&&p.scrollHeight>p.clientHeight+1){
    var up=e.deltaY<0,top=p.scrollTop<=0,bot=p.scrollTop+p.clientHeight>=p.scrollHeight-1;
    if(!((up&&top)||(!up&&bot)))return;   /* texte long : la molette fait d'abord défiler le texte */
  }
  var d=Math.abs(e.deltaX)>Math.abs(e.deltaY)?e.deltaX:e.deltaY;
  if(e.deltaMode===1)d*=16;
  e.preventDefault();
  var max=rail.scrollWidth-rail.clientWidth;
  target=Math.min(Math.max((target==null?rail.scrollLeft:target)+d,0),max);
  if(!raf)raf=requestAnimationFrame(tick);
},{passive:false});

/* Glisser à la souris */
var drag=false,moved=false,x0=0,s0=0;
rail.addEventListener('mousedown',function(e){
  if(mobile()||e.button!==0||e.target.closest('a,button,.panel'))return;
  drag=true;moved=false;x0=e.clientX;s0=rail.scrollLeft;target=null;
  if(raf){cancelAnimationFrame(raf);raf=null}
  rail.classList.add('drag');
});
window.addEventListener('mousemove',function(e){
  if(!drag)return;var d=x0-e.clientX;if(Math.abs(d)>5)moved=true;rail.scrollLeft=s0+d;
});
window.addEventListener('mouseup',function(){drag=false;rail.classList.remove('drag')});
rail.addEventListener('click',function(e){if(moved){e.stopPropagation();e.preventDefault();moved=false}},true);

rail.addEventListener('keydown',function(e){
  var step=Math.round(window.innerWidth*.5);
  if(e.key==='ArrowRight'){target=null;rail.scrollBy({left:step,behavior:'smooth'})}
  if(e.key==='ArrowLeft'){target=null;rail.scrollBy({left:-step,behavior:'smooth'})}
});

/* Visionneuse plein écran */
function open(i){cur=i;var s=slides[i];lbi.src=s.dataset.src;lbi.alt=s.dataset.caption;
  lbc.textContent=s.dataset.caption+' — '+(i+1)+' / '+slides.length;lb.classList.add('on')}
function step(d){open((cur+d+slides.length)%slides.length)}
function close(){lb.classList.remove('on')}
slides.forEach(function(s,i){s.addEventListener('click',function(){open(i)});
  s.addEventListener('keydown',function(e){if(e.key==='Enter')open(i)})});
lb.querySelector('.x').onclick=close;
lb.querySelector('.pv').onclick=function(){step(-1)};
lb.querySelector('.nx').onclick=function(){step(1)};
lb.addEventListener('click',function(e){if(e.target===lb)close()});
document.addEventListener('keydown',function(e){
  if(!lb.classList.contains('on'))return;
  if(e.key==='Escape')close();if(e.key==='ArrowRight')step(1);if(e.key==='ArrowLeft')step(-1);
});
})();
