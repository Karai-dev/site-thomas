#!/usr/bin/env python3
"""
Générateur de site — Thomas Cytrynowicz
==========================
Lance ce script depuis la racine de ton site :

    python3 generate_site.py

Il parcourt le dossier images/, détecte automatiquement chaque série (= un dossier qui
contient un fichier serie.json et ses photos) et génère, en fichiers HTML indépendants :

    index.html               accueil : 3 grands titres, une grille de séries par catégorie
                             (avec onglets pour Commandes), à propos, contact
    series/<slug>.html       UNE PAGE PAR SÉRIE (texte à gauche, photos en défilement horizontal)
    assets/style.css         feuille de style commune
    assets/series.js         script commun des pages de série

AJOUTER UNE SÉRIE
    1. Crée un dossier avec ses photos, par exemple  images/fine-art/white-village/
    2. Crée son fichier serie.json (modèle automatique) :
           python3 generate_site.py --init images/fine-art/white-village
       puis remplis le titre, le lieu, l'année, le texte.
    3. Relance :  python3 generate_site.py
       La série apparaît sur l'accueil et sa page est créée. Rien d'autre à toucher.

Aucune dépendance : Python 3 seul.

CHAMPS DISPONIBLES DANS serie.json  (seul "title" est vraiment nécessaire)
    title       Titre de la série
    category    Catégorie : documentaire, commandes, fine-art ou lifestyle
                (les noms de dossiers "documentary" et "commissions" sont aussi acceptés).
                Si la série est rangée dans un dossier de catégorie (ex. images/commissions/…),
                c'est le DOSSIER qui décide ; ce champ ne sert que pour une série rangée ailleurs.
    tab         Commandes uniquement : ong, pol ou inst
    location    Lieu, affiché sous le titre
    year        Année, ex. "2026" ou "2022–2026" (sert aussi à trier : récentes d'abord)
    description Liste de paragraphes. Liens : [mot](https://adresse)
    cover       Nom du fichier utilisé pour la vignette (sinon la 1re image)
    cover_pos   Cadrage de la vignette, ex. "40% 30%" (gauche-droite, haut-bas)
    wide        true = grande vignette (format paysage), false = vignette verticale
    hero        Photo de la grande image d'accueil (sinon la couverture)
    hero_pos    Cadrage de la grande image d'accueil (sinon celui de la vignette)
    order       Position dans la grille (1 = en premier) ; 1000 = tri par année
    captions    Titres des photos : {"Karai-1.jpg": "Titre de la photo"}
    slug        Nom de la page : series/<slug>.html (sinon le nom du dossier)

Exemple complet :
    {
      "title": "Desert Tales",
      "category": "fine-art",
      "location": "Mauritania",
      "year": "2024",
      "description": ["First paragraph.", "Second paragraph."],
      "cover": "Karai-3.jpg",
      "cover_pos": "40% 50%",
      "wide": true,
      "hero": "Karai-5.jpg",
      "hero_pos": "50% 30%",
      "order": 1,
      "captions": {"Karai-1.jpg": "Title of the first photo"}
    }
"""

import os
import re
import html
import struct
import sys
import json
import unicodedata
from urllib.parse import quote

# ============================================================
#  ⚙️  CONFIG — modifie uniquement cette section
# ============================================================

SITE_NAME   = "Thomas Cytrynowicz"
SITE_TITLE  = "Thomas Cytrynowicz — Photographer"
LANG        = "en"
EMAIL       = "thomas@karai.org"
LINKS       = [("Instagram", "https://www.instagram.com/thomcytry"), ("LinkedIn", "https://www.linkedin.com/in/thomas-cytrynowicz/"), ("Karai", "https://www.karai.org")]
INTRO       = [
    "Photographer and Expedition leader.", 
    "Reportage, lifestyle and fine art.", 
    "For organisations and exhibitions."
]

ABOUT_TEXT  = [                      # une ligne entre guillemets = un paragraphe (séparés par une ligne vide)
    "A photographer, filmmaker, and expedition leader, Thomas works on documentary projects exploring the interdependence between communities and their environment. With a passion for nomadic peoples, he accompanies families on their seasonal migrations and explores community relationships along the way.",
    "Thomas organizes photography expeditions around the world, from Madagascar to Mongolia, Mauritania and India with [Karai Expeditions](https://karai.org/expeditions).",
    "He places great importance on the human connections his work allows him to make and also puts his experience to use for NGOs and institutions.",
    "He is represented by Picpus gallery."
]
ABOUT_ROWS  = [                      # (label, value) — delete the list to show nothing
    ("Clients", "VSF Belgium, MSF Belgium, Instant News Services, Check-in Films, AFdB, EU institutions, UNICEF, Institut du Chamanisme et du Nomadisme Mongol "),
    ("Documentaries", "The Circle - A Mongolian Adventure, Digital Cultures, Inside Nadaam, Transhumances"),
    ("Exhibitions", "Transhumances, Brussels & Strasbourg, 2026"),
]

# Interface texts
T = {
    "about": "About", "contact": "Contact", "all": "All",
    "year": "Year", "photos": "Photographs", "category": "Category",
    "next": "Next series", "back_end": "Back", "end_label": "End of the series",
    "empty": "No series in this category yet.",
    "close": "Close", "prev": "Previous", "following": "Next",
    "rail_label": "Photographs of the series, horizontal scroll",
}

# --- Catégories (l'ordre = l'ordre du menu et de l'accueil) ---
# "id" = identifiant interne (sert aussi d'ancre : index.html#commandes).
# "folders" = noms de dossiers dans images/ qui correspondent à cette catégorie.
# "title", "subtitle", "description" = textes affichés sur le site.
# "tabs" est optionnel : (identifiant, libellé, texte affiché sous les onglets)
CATEGORIES = [
    {
        "id": "documentaire", "title": "Documentary", "folders": ["documentary"],
        "subtitle": "Long-term projects",
        "description": "Series built over time, presented as complete projects.",
    },
    {
        "id": "commandes", "title": "Commissions", "folders": ["commissions"],
        "subtitle": "NGOs, political affairs, institutions",
        "description": "Reportage and portraits made for organisations, political actors and institutions.",
        "tabs": [
            ("ong",  "NGOs", "Fieldwork, programmes and testimonies for humanitarian and development organisations."),
            ("pol",  "Political affairs", "Campaigns, official visits and portraits of elected officials and leaders."),
            ("inst", "Institutions", "Institutional communication, events and team portraits."),
        ],
    },
    {
        "id": "fine-art", "title": "Fine art",
        "subtitle": "Prints and editions",
        "description": "Series available as prints, in limited and numbered editions.",
    },
    {
        "id": "lifestyle", "title": "Lifestyle",
        "subtitle": "Hospitality, travel, art of living",
        "description": "Images for hotels, travel and brands: places, atmospheres and ways of living.",
    },
]

# --- Séries : détectées automatiquement ---------------------
# Chaque dossier de SERIES_ROOT contenant un fichier serie.json est une série.
SERIES_ROOT = "images"
META_FILE   = "serie.json"

# Format des vignettes de l'accueil (largeur / hauteur). Dans une même rangée,
# toutes les vignettes ont la même hauteur ; seule leur largeur change.
COVER_RATIO      = 4 / 5     # vignette normale (verticale)
COVER_RATIO_WIDE = 4 / 3     # grande vignette ("wide": true dans serie.json)

# Dossiers de sortie et extensions acceptées
SERIES_FOLDER   = "series"
ASSETS_FOLDER   = "assets"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".webp", ".png", ".gif"}

# ============================================================
#  🔧  SCRIPT — ne pas modifier en dessous
# ============================================================

CSS = r"""
:root{
  --bg:#f5f5f3;--ink:#161616;--mute:#76766f;--line:#dcdcd8;--t1:#d3d3cf;
  --h:64px;box-sizing:border-box;color-scheme:light;
  padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px);
}
@media (prefers-color-scheme:dark){:root{--bg:#121212;--ink:#ececea;--mute:#8d8d88;--line:#2c2c2a;--t1:#222221;color-scheme:dark}}
*{box-sizing:border-box}
html{scroll-padding-top:var(--h);scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Hanken Grotesk",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;font-weight:300;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
a:focus-visible,button:focus-visible{outline:2px solid var(--ink);outline-offset:3px}
[hidden]{display:none!important}
header{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;height:var(--h);display:flex;justify-content:space-between;align-items:center;padding:0 clamp(20px,4vw,56px);background:var(--bg)}
.name{font-weight:500;letter-spacing:.01em;white-space:nowrap}
nav{display:flex;gap:clamp(14px,2.4vw,32px);font-size:.9rem}
nav a{color:var(--mute);transition:color .2s}
nav a:hover,nav a[aria-current]{color:var(--ink)}
h2{margin:0;font-weight:300;font-size:clamp(1.8rem,3.6vw,3rem);letter-spacing:-.03em;line-height:1.1}
.band{padding:clamp(40px,6vw,80px) clamp(20px,4vw,56px) 0}
.cat{padding-top:clamp(56px,9vw,120px)}

/* Accueil */
.index{display:grid;grid-template-columns:1.2fr 1fr;gap:clamp(24px,5vw,80px);min-height:calc(100svh - 140px);align-items:center;padding:40px clamp(20px,4vw,56px) 80px}
.intro{margin-bottom:36px}
.lead{max-width:34ch;margin:0;color:var(--mute);font-size:1.05rem}
.lead a{color:var(--ink);border-bottom:1px solid currentColor}
.index ul{list-style:none;margin:0;padding:0}
.index li a{display:flex;align-items:baseline;justify-content:space-between;gap:16px;padding:clamp(14px,2.4vw,28px) 0;border-bottom:1px solid var(--line);font-size:clamp(2.2rem,6.4vw,5.6rem);line-height:1;letter-spacing:-.035em;color:var(--mute);transition:color .25s}
.index li:first-child a{border-top:1px solid var(--line)}
.index li a small{font-size:.9rem;letter-spacing:0;white-space:nowrap}
.index li a:hover,.index li a:focus-visible{color:var(--ink)}
.preview{aspect-ratio:4/5;width:100%;max-height:72vh;justify-self:end;background:var(--t1) center/cover no-repeat}
.about{display:grid;grid-template-columns:1fr 1fr;gap:clamp(24px,5vw,80px)}
.about>div{max-width:52ch}
.about p{margin:0 0 1.4em;max-width:52ch;text-align:justify;hyphens:auto;-webkit-hyphens:auto}
.about p a,.about dd a,.panel p.d a{color:var(--ink);border-bottom:1px solid currentColor;transition:opacity .2s}
.about p a:hover,.about dd a:hover,.panel p.d a:hover{opacity:.6}
.about dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:6px 24px;color:var(--mute);font-size:.95rem}
.about dd{margin:0;color:var(--ink)}
.mail{font-size:clamp(1.6rem,4vw,3.2rem);letter-spacing:-.03em;border-bottom:1px solid var(--ink);display:inline-block;line-height:1.2}
footer{padding:80px clamp(20px,4vw,56px) 40px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:16px;color:var(--mute);font-size:.85rem}

/* Page de catégorie */
.head{display:flex;justify-content:space-between;align-items:end;gap:24px;flex-wrap:wrap;margin-bottom:28px}
.desc{max-width:52ch;color:var(--mute);margin:10px 0 0}
.filters{display:flex;gap:6px;flex-wrap:wrap}
.filters button{font:inherit;font-size:.88rem;background:none;border:1px solid var(--line);color:var(--mute);padding:6px 14px;border-radius:99px;cursor:pointer;transition:all .2s}
.filters button:hover{color:var(--ink);border-color:var(--ink)}
.filters button[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.fdesc{margin:-10px 0 24px;color:var(--mute);font-size:.92rem}
.grid{--ch:clamp(200px,34vw,560px);display:flex;flex-wrap:wrap;gap:clamp(18px,2.4vw,36px) clamp(10px,1.4vw,20px);align-items:flex-start}
.card{display:block;min-width:0;flex-basis:calc(var(--a) * var(--ch));max-width:calc(var(--a) * var(--ch) * 1.3)}
.cv{position:relative;overflow:hidden;background:var(--t1);aspect-ratio:var(--a)}
.cv i{position:absolute;inset:0;background:center/cover no-repeat;transition:transform .6s cubic-bezier(.25,.46,.45,.94)}
.card:hover .cv i,.card:focus-visible .cv i{transform:scale(1.03)}
.cap{display:flex;justify-content:space-between;gap:12px;padding-top:10px;font-size:.95rem}
.cap span:last-child{color:var(--mute)}
.none{color:var(--mute);flex:1 1 100%}

/* Page de série */
body.series{overflow:hidden}
.s{height:calc(100svh - var(--h) - env(safe-area-inset-top,0px) - env(safe-area-inset-bottom,0px))}
.panel{width:min(440px,34vw);flex:none;height:100%;padding:32px 40px 28px clamp(20px,4vw,56px);border-right:1px solid var(--line);display:flex;flex-direction:column;overflow-y:auto;scrollbar-width:none}
.panel::-webkit-scrollbar{display:none}
.back{font-size:.85rem;color:var(--mute);margin-bottom:28px;align-self:flex-start;transition:color .2s}
.back:hover{color:var(--ink)}
.panel h1{margin:0 0 6px;font-weight:300;font-size:clamp(2rem,3vw,2.8rem);line-height:1.05;letter-spacing:-.035em}
.sub{margin:0 0 28px;color:var(--mute)}
.meta{margin:0 0 24px;padding:0;display:grid;grid-template-columns:auto 1fr;font-size:.9rem;border-top:1px solid var(--line)}
.meta dt,.meta dd{margin:0;padding:10px 0;border-bottom:1px solid var(--line)}
.meta dt{color:var(--mute);padding-right:24px}.meta dd{text-align:right}
.panel p.d{margin:0 0 1em;color:var(--mute);max-width:46ch}
.prog{position:fixed;z-index:4;left:50%;bottom:calc(12px + env(safe-area-inset-bottom,0px));transform:translateX(-50%);width:120px;text-align:center;font-size:.75rem;color:var(--mute);pointer-events:none}
.prog b{font-weight:400;color:var(--ink)}
.bar{height:1px;background:var(--line);margin-top:10px}.bar i{display:block;height:1px;background:var(--ink);width:0;transition:width .15s}
.rail{--rh:calc(100svh - var(--h) - env(safe-area-inset-top,0px) - env(safe-area-inset-bottom,0px) - 76px);height:100%;display:flex;overflow-x:auto;overflow-y:hidden;scrollbar-width:none}
.rail.drag{cursor:grabbing;user-select:none}
.photos{flex:none;display:flex;align-items:flex-start;gap:20px;padding:24px clamp(20px,2.4vw,40px) 52px}
.photos::-webkit-scrollbar{display:none}
.rail::-webkit-scrollbar{display:none}
.slide{flex:none;height:var(--rh);margin:0;position:relative;background:var(--t1);overflow:hidden;cursor:zoom-in}
.slide img{width:100%;height:100%;object-fit:contain;display:block;-webkit-user-drag:none;user-select:none}
.slide figcaption{position:absolute;inset:auto 0 0 0;padding:36px 16px 12px;font-size:.82rem;color:#fff;background:linear-gradient(transparent,rgba(0,0,0,.55));opacity:0;transition:opacity .25s;display:flex;justify-content:space-between;gap:12px}
.slide:hover figcaption,.slide:focus-visible figcaption{opacity:1}
.next{flex:none;width:300px;height:var(--rh);display:flex;flex-direction:column;justify-content:flex-end;padding:0 8px 8px 24px;color:var(--mute)}
.next a{font-size:clamp(1.6rem,2.4vw,2.2rem);letter-spacing:-.03em;color:var(--ink);border-bottom:1px solid var(--ink);align-self:flex-start;line-height:1.2;margin-top:6px}
.lb{position:fixed;inset:0;z-index:20;background:var(--bg);display:none;flex-direction:column;align-items:center;justify-content:center;gap:14px;padding:56px 16px}
.lb.on{display:flex}
.lb img{max-width:min(96vw,1600px);max-height:calc(100svh - 150px);object-fit:contain}
.lb p{margin:0;color:var(--mute);font-size:.88rem}
.lb button{position:absolute;font:inherit;background:none;border:0;color:var(--ink);cursor:pointer;padding:12px 16px;font-size:.9rem}
.lb .x{top:12px;right:12px}.lb .pv{left:8px;top:50%}.lb .nx{right:8px;top:50%}

@media (max-width:820px){
  .index,.about{grid-template-columns:1fr}.preview{display:none}
  :root{--h:96px}
  header{flex-direction:column;align-items:flex-start;justify-content:center;gap:4px}
  nav{gap:2px 12px;font-size:.78rem;flex-wrap:wrap}
  nav a{white-space:nowrap}
  .index li a{flex-direction:column;align-items:flex-start;gap:8px}
  .index li a small{white-space:normal}
  .card{flex-basis:calc(50% - 5px);max-width:calc(50% - 5px)}.card.w{flex-basis:100%;max-width:none}
  body.series{overflow:auto}
  .s{height:auto}
  .rail{display:block;height:auto;overflow:visible}
  .panel{width:auto;height:auto;border:0;padding:20px;overflow:visible}
  .prog{display:none}
  .photos{height:64svh;overflow-x:auto;overflow-y:hidden;padding:0 20px 28px;scrollbar-width:none;--rh:calc(64svh - 28px)}
  .next{width:220px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}html{scroll-behavior:auto}}
"""

SERIES_JS = r"""(function(){
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
"""

HOME_JS = r"""(function(){
var p=document.getElementById('prev');
[].forEach.call(document.querySelectorAll('#idx a'),function(a){
  function on(){if(a.dataset.img){p.style.backgroundImage='url("'+a.dataset.img+'")';p.style.backgroundPosition=a.dataset.pos||'50% 50%'}}
  a.addEventListener('mouseenter',on);a.addEventListener('focus',on);
});
var q=new URLSearchParams(location.search).get('tab');
[].forEach.call(document.querySelectorAll('section.cat'),function(sec){
  var btns=[].slice.call(sec.querySelectorAll('.filters button'));if(!btns.length)return;
  var cards=[].slice.call(sec.querySelectorAll('.card')),fd=sec.querySelector('.fdesc'),none=sec.querySelector('.none');
  function set(k){
    btns.forEach(function(b){b.setAttribute('aria-pressed',b.dataset.k===k)});
    var n=0;cards.forEach(function(c){var ok=k==='all'||c.dataset.k===k;c.hidden=!ok;if(ok)n++});
    var b=btns.filter(function(b){return b.dataset.k===k})[0];
    fd.textContent=b?b.dataset.d:'';fd.hidden=!fd.textContent;none.hidden=n>0;
  }
  btns.forEach(function(b){b.addEventListener('click',function(){set(b.dataset.k)})});
  set(btns.some(function(b){return b.dataset.k===q})?q:'all');
});
})();
"""


# ---------- Utilitaires ----------

def esc(s):
    return html.escape(str(s), quote=True)


def rich(text):
    """Échappe le texte, transforme [mot](adresse) en lien hypertexte et \\n en retour à la ligne.
    Les adresses http(s) s'ouvrent dans un nouvel onglet."""
    def link(m):
        label, href = m.group(1), m.group(2)
        ext = ' target="_blank" rel="noopener noreferrer"' if href.startswith(("http://", "https://")) else ""
        return f'<a href="{href}"{ext}>{label}</a>'
    out = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, esc(text))
    return out.replace("\n", "<br>")      # \n dans un texte = retour à la ligne sans nouveau paragraphe


def url(path):
    """Encode un chemin relatif pour une URL (espaces, accents...)."""
    # NFC : les accents sont encodés comme GitHub/le serveur stockent les noms de fichiers
    path = unicodedata.normalize("NFC", path)
    return "/".join(quote(part) for part in path.replace("\\", "/").split("/"))


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def exif_orientation(tiff):
    """Lit le tag d'orientation EXIF (1 = normal, 6/8 = pivoté de 90°)."""
    try:
        e = "<" if tiff[:2] == b"II" else ">"
        off = struct.unpack(e + "I", tiff[4:8])[0]
        n = struct.unpack(e + "H", tiff[off:off + 2])[0]
        for i in range(n):
            p = off + 2 + i * 12
            if struct.unpack(e + "H", tiff[p:p + 2])[0] == 0x0112:
                return struct.unpack(e + "H", tiff[p + 8:p + 10])[0]
    except Exception:
        pass
    return 1


def get_image_dimensions(filepath):
    """Lit les dimensions réelles de l'image sans dépendance externe."""
    try:
        with open(filepath, "rb") as f:
            data = f.read(30)

        if data[:2] == b"\xff\xd8":  # JPEG
            with open(filepath, "rb") as f:
                f.read(2)
                orientation = 1
                while True:
                    marker = f.read(2)
                    if len(marker) < 2 or marker[0] != 0xFF:
                        break
                    length = struct.unpack(">H", f.read(2))[0]
                    if marker[1] in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                                     0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        d = f.read(5)
                        h = struct.unpack(">H", d[1:3])[0]
                        w = struct.unpack(">H", d[3:5])[0]
                        if orientation in (5, 6, 7, 8):  # photo pivotée par l'EXIF : le navigateur l'affiche tournée
                            w, h = h, w
                        return w, h
                    seg = f.read(length - 2)
                    if marker[1] == 0xE1 and seg[:6] == b"Exif\x00\x00":
                        orientation = exif_orientation(seg[6:])

        elif data[:8] == b"\x89PNG\r\n\x1a\n":  # PNG
            return struct.unpack(">I", data[16:20])[0], struct.unpack(">I", data[20:24])[0]

        elif data[:6] in (b"GIF87a", b"GIF89a"):  # GIF
            return struct.unpack("<HH", data[6:10])

        elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":  # WebP
            if data[12:16] == b"VP8 ":
                return (struct.unpack("<H", data[26:28])[0] & 0x3FFF,
                        struct.unpack("<H", data[28:30])[0] & 0x3FFF)
            if data[12:16] == b"VP8L":
                bits = struct.unpack("<I", data[21:25])[0]
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
            if data[12:16] == b"VP8X":
                return (struct.unpack("<I", data[24:27] + b"\x00")[0] + 1,
                        struct.unpack("<I", data[27:30] + b"\x00")[0] + 1)
    except Exception:
        pass
    return None, None


def read_images(folder):
    """Retourne la liste des images d'un dossier, avec leurs dimensions."""
    if not os.path.isdir(folder):
        print(f"⚠️  Dossier introuvable : {folder}")
        return []
    files = sorted((f for f in os.listdir(folder)
                    if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS), key=natural_key)
    out = []
    for f in files:
        w, h = get_image_dimensions(os.path.join(folder, f))
        if not w:
            print(f"  ⚠️  Dimensions illisibles : {f} — paysage 3/2 par défaut")
            w, h = 3, 2
        out.append({"file": f, "w": w, "h": h})
    return out


def humanize(name):
    return re.sub(r"[-_]+", " ", name).strip().capitalize()


def year_of(s):
    years = re.findall(r"\d{4}", str(s.get("year", "")))
    return int(max(years)) if years else 0


def resolve_category(name):
    """Retourne l'id de catégorie correspondant à un id ou à un nom de dossier (sinon "")."""
    name = (name or "").strip().lower()
    for c in CATEGORIES:
        if name == c["id"].lower() or name in [f.lower() for f in c.get("folders", [])]:
            return c["id"]
    return ""


def load_series():
    """Parcourt SERIES_ROOT et retourne la liste des séries déclarées par un serie.json."""
    if not os.path.isdir(SERIES_ROOT):
        print(f"⚠️  Dossier introuvable : {SERIES_ROOT}/")
        return []
    found, slugs = [], set()
    for root, dirs, files in os.walk(SERIES_ROOT):
        dirs.sort(key=natural_key)
        folder = root.replace(os.sep, "/")
        has_images = any(os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS for f in files)
        if META_FILE not in files:
            if has_images:
                print(f"⚠️  {folder} contient des images mais pas de {META_FILE} — ignoré "
                      f"(crée-le avec : python3 generate_site.py --init {folder})")
            continue
        try:
            with open(os.path.join(root, META_FILE), encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as e:
            print(f"⚠️  {folder}/{META_FILE} illisible ({e}) — ignoré")
            continue
        base = os.path.basename(root)
        parent = os.path.basename(os.path.dirname(root))
        desc = meta.get("description", [])
        if isinstance(desc, str):
            desc = [p.strip() for p in re.split(r"\n\s*\n", desc) if p.strip()]
        s = {
            "slug": meta.get("slug") or base,
            "category": "",
            "tab": meta.get("tab", ""),
            "title": meta.get("title") or humanize(base),
            "location": meta.get("location", ""),
            "year": str(meta.get("year", "")),
            "description": desc,
            "folder": folder,
            "cover": meta.get("cover", ""),
            "cover_pos": meta.get("cover_pos", "50% 50%"),
            "hero": meta.get("hero", ""),
            "hero_pos": meta.get("hero_pos", ""),
            "wide": bool(meta.get("wide", False)),
            "captions": meta.get("captions", {}),
            "order": meta["order"] if isinstance(meta.get("order"), (int, float)) else 1000,
        }
        # Catégorie : le dossier parent décide ; sinon le champ "category" du serie.json
        from_folder = resolve_category(parent)
        from_json = resolve_category(meta.get("category")) or meta.get("category", "")
        s["category"] = from_folder or from_json
        if from_folder and meta.get("category") and from_json != from_folder:
            print(f"⚠️  « {s['title']} » : serie.json indique « {meta.get('category')} » mais la série est "
                  f"dans le dossier « {parent} » → classée dans « {from_folder} » "
                  f"(corrige ou supprime le champ category de {folder}/{META_FILE})")
        if s["slug"] in slugs:
            print(f"⚠️  Identifiant « {s['slug']} » en double ({folder}) — ignoré")
            continue
        cat = next((c for c in CATEGORIES if c["id"] == s["category"]), None)
        if s["tab"] and cat and s["tab"] not in [t[0] for t in cat.get("tabs", [])]:
            print(f"⚠️  « {s['title']} » : l'onglet « {s['tab']} » n'existe pas dans « {cat['id']} » "
                  f"— la série n'apparaîtra que sous « All » (corrige le champ tab ou category)")
        slugs.add(s["slug"])
        found.append(s)
    found.sort(key=lambda s: (s["order"], -year_of(s), s["title"].lower()))
    return found


def init_series(folder):
    """Crée un serie.json modèle dans le dossier indiqué."""
    folder = folder.rstrip("/\\")
    if not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, META_FILE)
    if os.path.exists(path):
        print(f"⚠️  {path} existe déjà — rien n'a été écrasé")
        return
    parent = os.path.basename(os.path.dirname(os.path.abspath(folder)))
    cat = resolve_category(parent)
    if not cat:
        cat = CATEGORIES[0]["id"]
        print(f"⚠️  Le dossier « {parent} » ne correspond à aucune catégorie — « {cat} » mise par défaut, "
              f"vérifie le champ category")
    meta = {"title": humanize(os.path.basename(os.path.abspath(folder))), "category": cat}
    if any(c["id"] == cat and c.get("tabs") for c in CATEGORIES):
        meta["tab"] = next(c["tabs"][0][0] for c in CATEGORIES if c["id"] == cat)
    meta.update({
        "location": "", "year": "", "description": ["Texte de présentation."],
        "cover": "", "cover_pos": "50% 50%", "wide": False,
        "hero": "", "hero_pos": "", "order": 1000, "captions": {},
    })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"✓  Modèle créé : {path} — remplis-le puis relance : python3 generate_site.py")


def cat_by_id(cid):
    return next(c for c in CATEGORIES if c["id"] == cid)


# ---------- Gabarits HTML ----------

def head(title, prefix):
    return f"""<!DOCTYPE html>
<html lang="{LANG}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@300;400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{prefix}{ASSETS_FOLDER}/style.css">
</head>"""


def header(prefix, current=None):
    cur = ' aria-current="page"'
    links = "".join(
        f'<a href="{prefix}index.html#{c["id"]}"{cur if c["id"] == current else ""}>{esc(c["title"])}</a>'
        for c in CATEGORIES)
    links += f'<a href="{prefix}index.html#about">{esc(T["about"])}</a>'
    links += f'<a href="{prefix}index.html#contact">{esc(T["contact"])}</a>'
    return f"""<header>
  <a class="name" href="{prefix}index.html">{esc(SITE_NAME)}</a>
  <nav aria-label="Navigation">{links}</nav>
</header>"""


def footer():
    # Les liens externes (http…) s'ouvrent dans un nouvel onglet
    ext = ' target="_blank" rel="noopener noreferrer"'
    social = " &nbsp; ".join(
        f'<a href="{esc(u)}"{ext if u.startswith(("http://", "https://")) else ""}>{esc(n)}</a>'
        for n, u in LINKS)
    return f'<footer><span>© {esc(SITE_NAME)}</span><span>{social}</span></footer>'


def cover_of(s):
    """Chemin (relatif à la racine) de la couverture de la série."""
    cover = s.get("cover") or s["images"][0]["file"]
    return f'{s["folder"]}/{cover}'


def section_html(c, live_series):
    mine = [s for s in live_series if s["category"] == c["id"]]
    tabs = c.get("tabs") or []
    filters = fdesc = ""
    if tabs:
        btns = f'<button aria-pressed="true" data-k="all" data-d="">{esc(T["all"])}</button>'
        btns += "".join(f'<button aria-pressed="false" data-k="{esc(k)}" data-d="{esc(d)}">{esc(lbl)}</button>'
                        for k, lbl, d in tabs)
        filters = f'<div class="filters" role="group" aria-label="{esc(c["title"])}">{btns}</div>'
        fdesc = '<p class="fdesc" hidden></p>'
    cards = ""
    for s in mine:
        pos = s.get("cover_pos", "50% 50%")
        k = f' data-k="{esc(s["tab"])}"' if s.get("tab") else ""
        a = COVER_RATIO_WIDE if s.get("wide") else COVER_RATIO
        cards += (f'      <a class="card{" w" if s.get("wide") else ""}" style="--a:{a:.4f};flex-grow:{round(a * 100)}" '
                  f'href="{SERIES_FOLDER}/{s["slug"]}.html"{k}>'
                  f'<div class="cv"><i style="background-image:url(\'{esc(url(cover_of(s)))}\');background-position:{esc(pos)}"></i></div>'
                  f'<div class="cap"><span>{esc(s["title"])}</span><span>{esc(s["year"])}</span></div></a>\n')
    none = f'      <p class="none"{"" if not mine else " hidden"}>{esc(T["empty"])}</p>\n'
    return f"""  <section class="band cat" id="{c["id"]}">
    <div class="head">
      <div><h2>{esc(c["title"])}</h2><p class="desc">{esc(c["description"])}</p></div>
      {filters}
    </div>
    {fdesc}
    <div class="grid">
{cards}{none}    </div>
  </section>
"""


def hero_of(s):
    """(chemin, cadrage) de la grande image d'accueil : champs hero / hero_pos, sinon la couverture."""
    img = f'{s["folder"]}/{s["hero"]}' if s.get("hero") else cover_of(s)
    pos = s.get("hero_pos") or s.get("cover_pos") or "50% 50%"
    return img, pos


def page_home(live_series):
    rows, first_img, first_pos = "", "", "50% 50%"
    for c in CATEGORIES:
        mine = [s for s in live_series if s["category"] == c["id"]]
        img, pos = (url(hero_of(mine[0])[0]), hero_of(mine[0])[1]) if mine else ("", "50% 50%")
        if img and not first_img:
            first_img, first_pos = img, pos
        rows += (f'<li><a href="#{c["id"]}" data-img="{esc(img)}" data-pos="{esc(pos)}"><span>{esc(c["title"])}</span>'
                 f'<small>{esc(c["subtitle"])}</small></a></li>\n        ')
    sections = "".join(section_html(c, live_series) for c in CATEGORIES)
    intro_items = [INTRO] if isinstance(INTRO, str) else INTRO     # texte seul ou liste de paragraphes
    intro_html = "".join(f'<p class="lead">{rich(p)}</p>' for p in intro_items)
    about_p = "".join(f"<p>{rich(p)}</p>" for p in ABOUT_TEXT)
    about_dl = ""
    if ABOUT_ROWS:
        about_dl = "<dl>" + "".join(f"<dt>{esc(k)}</dt><dd>{rich(v)}</dd>" for k, v in ABOUT_ROWS) + "</dl>"
    style = (f' style="background-image:url(\'{esc(first_img)}\');background-position:{esc(first_pos)}"'
             if first_img else "")
    return f"""{head(SITE_TITLE, "")}
<body>
{header("")}
<main>
  <div class="index">
    <div>
      <div class="intro">{intro_html}</div>
      <ul id="idx">
        {rows}</ul>
    </div>
    <div class="preview" id="prev"{style} aria-hidden="true"></div>
  </div>
{sections}  <section class="band cat" id="about">
    <div class="about"><h2>{esc(T["about"])}</h2><div>{about_p}{about_dl}</div></div>
  </section>
  <section class="band" id="contact"><a class="mail" href="mailto:{esc(EMAIL)}">{esc(EMAIL)}</a></section>
</main>
{footer()}
<script>{HOME_JS}</script>
</body>
</html>"""


def page_series(s, siblings):
    c = cat_by_id(s["category"])
    total = len(s["images"])
    kind = c["title"]
    back = f'../index.html#{c["id"]}'
    if s.get("tab"):
        label = next((lbl for k, lbl, _ in c.get("tabs", []) if k == s["tab"]), "")
        if label:
            kind = f'{c["title"]} · {label}'
            back = f'../index.html?tab={s["tab"]}#{c["id"]}'
    captions = s.get("captions", {})
    slides = ""
    for i, im in enumerate(s["images"]):
        src = url(f'../{s["folder"]}/{im["file"]}')
        cap = captions.get(im["file"], s["title"])
        slides += (f'    <figure class="slide" tabindex="0" data-src="{esc(src)}" data-caption="{esc(cap)}" '
                   f'style="aspect-ratio:{im["w"]}/{im["h"]}">'
                   f'<img src="{esc(src)}" alt="{esc(cap)} — {i + 1}" loading="{"eager" if i < 3 else "lazy"}" decoding="async">'
                   f'<figcaption><span>{esc(cap)}</span><span>{i + 1:02d} / {total:02d}</span></figcaption></figure>\n')
    # Série suivante (même catégorie), sinon retour à la catégorie
    if len(siblings) > 1:
        nxt = siblings[(siblings.index(s) + 1) % len(siblings)]
        end = f'{esc(T["next"])}<a href="{nxt["slug"]}.html">{esc(nxt["title"])}</a>'
    else:
        end = f'{esc(T["back_end"])}<a href="{back}">{esc(c["title"])}</a>'
    desc = "".join(f'<p class="d">{rich(p)}</p>' for p in s["description"])
    return f"""{head(s["title"] + " — " + SITE_NAME, "../")}
<body class="series">
{header("../", c["id"])}
<main class="s">
  <div class="rail" id="rail" tabindex="0" aria-label="{esc(T["rail_label"])}">
  <aside class="panel">
    <a class="back" href="{back}">← {esc(c["title"])}</a>
    <h1>{esc(s["title"])}</h1>
    <p class="sub">{esc(s["location"])}</p>
    <dl class="meta">
      <dt>{esc(T["year"])}</dt><dd>{esc(s["year"])}</dd>
      <dt>{esc(T["photos"])}</dt><dd>{total}</dd>
      <dt>{esc(T["category"])}</dt><dd>{esc(kind)}</dd>
    </dl>
    {desc}
  </aside>
  <div class="photos">
{slides}    <div class="next">{end}</div>
  </div>
  </div>
</main>
<div class="prog" aria-hidden="true"><b id="c-n">01</b> / {total:02d}<div class="bar"><i id="c-b"></i></div></div>
<div class="lb" id="lb" role="dialog" aria-modal="true">
  <button class="x" aria-label="{esc(T["close"])}">{esc(T["close"])}</button>
  <button class="pv" aria-label="{esc(T["prev"])}">‹</button>
  <img id="lb-i" alt=""><p id="lb-c"></p>
  <button class="nx" aria-label="{esc(T["following"])}">›</button>
</div>
<script src="../{ASSETS_FOLDER}/series.js"></script>
</body>
</html>"""


# ---------- Programme principal ----------

def write(path, content):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--init":
        init_series(sys.argv[2])
        return
    live = []
    for s in load_series():
        if s["category"] not in [c["id"] for c in CATEGORIES]:
            print(f"⚠️  « {s['title']} » : catégorie inconnue « {s['category']} » — ignorée (voir CATEGORIES ou le champ category de {META_FILE})")
            continue
        images = read_images(s["folder"])
        if not images:
            print(f"⚠️  « {s['title']} » ignorée (aucune image dans {s['folder']})")
            continue
        s = dict(s, images=images)
        if s.get("cover") and s["cover"] not in [i["file"] for i in images]:
            print(f"  ⚠️  Couverture introuvable : {s['cover']} — première image utilisée")
            s.pop("cover")
        if s.get("hero") and s["hero"] not in [i["file"] for i in images]:
            print(f"  ⚠️  Image d'accueil (hero) introuvable : {s['hero']} — couverture utilisée")
            s["hero"] = ""
        live.append(s)
        print(f"✓  {s['title']} : {len(images)} image(s)")

    if not live:
        print(f"Aucune série générée. Vérifie que {SERIES_ROOT}/ contient des dossiers avec un {META_FILE} et des images.")
        return

    write(os.path.join(ASSETS_FOLDER, "style.css"), CSS.strip() + "\n")
    write(os.path.join(ASSETS_FOLDER, "series.js"), SERIES_JS)
    write("index.html", page_home(live))
    for s in live:
        siblings = [x for x in live if x["category"] == s["category"]]
        write(os.path.join(SERIES_FOLDER, f'{s["slug"]}.html'), page_series(s, siblings))

    print(f"\n✓  Site généré : index.html + {len(live)} pages de série")
    print(f"   Pages de série : /{SERIES_FOLDER}/<slug>.html")


if __name__ == "__main__":
    main()
