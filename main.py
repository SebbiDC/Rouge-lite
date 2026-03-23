import asyncio
"""
HORDE SURVIVOR v3
Controls: WASD/Arrows=move | Q=special | E=interact | F=parry(sword)
          1/2/3 or CLICK = choose upgrade | TAB=card log | I=index
"""
import pygame, math, random, sys, json, os

W, H = 1280, 720
FPS   = 60
screen = None
clock  = None

SAVE_FILE = "horde_save.json"

# ═══════ PALETTE ═══════════════════════════════════════════════════════════════
BG=(10,10,18); GRID_C=(20,20,35); PLAYER_C=(80,200,255)
BULLET_C=(255,240,80); CHAIN_C=(120,80,255); SAW_C=(200,230,255)
SWORD_C=(180,220,255); RAY_C=(60,255,180); LIGHTNING_C=(200,160,255)
SHOTGUN_C=(255,160,60); PLASMA_C=(100,200,255); SNIPER_C=(255,220,80)
ENEMY_C=(220,50,50); ELITE_C=(255,120,20); BOSS_C=(200,0,200)
XP_C=(60,255,120); HP_BG=(60,0,0); HP_FG=(220,50,50)
XP_BG=(0,40,20); XP_FG=(60,255,120); WHITE=(255,255,255)
GRAY=(150,150,150); DGRAY=(40,40,55); FLASH_C=(255,255,255)
NOVA_C=(255,200,60); WARN_C=(255,60,60); COIN_C=(255,215,0)
SUPER_C=(255,100,255); STRUCT_C=(80,200,200); EVENT_C=(255,180,60)
PARRY_C=(180,255,80)

RANGED_FOV=math.pi*0.65

WEAPON_COLORS={"pistol":BULLET_C,"sword":SWORD_C,"raygun":RAY_C,
               "lightning":LIGHTNING_C,"shotgun":SHOTGUN_C,"plasma":PLASMA_C,"sniper":SNIPER_C}

font_huge=None
font_big=None
font_med=None
font_sm=None
font_xs=None

# ═══════ SAVE / LOAD ═══════════════════════════════════════════════════════════
DEFAULT_SAVE={"supercoins":0,"meta_upgrades":{},"super_tier_unlocked":{},
              "super_tier_levels":{},"total_runs":0,"total_kills":0,"best_wave":0,
              "seen_structures":[],"seen_events":[]}

def load_save():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE,"r") as f:
                data=json.load(f)
                for k,v in DEFAULT_SAVE.items():
                    if k not in data: data[k]=v
                return data
        except: pass
    return dict(DEFAULT_SAVE)

def write_save(data):
    with open(SAVE_FILE,"w") as f: json.dump(data,f,indent=2)

def calc_supercoins(wave,level,kills,boss_kills):
    return max(1, wave*3+level*2+kills//8+boss_kills*15)

# ═══════ META UPGRADES ═════════════════════════════════════════════════════════
META_UPGRADES=[
    ("m_hp","IRON CONSTITUTION","+20 starting max HP",5,8,"max_hp",20),
    ("m_xp","SCHOLAR","+8% XP gain",4,6,"xp_mult",0.08),
    ("m_speed","TRAVELER","+0.3 base move speed",5,5,"speed",0.3),
    ("m_dmg","WARPATH","+8 base damage",6,6,"dmg",8),
    ("m_regen","VITALITY","+1 HP regen/s",4,5,"hp_regen",1),
    ("m_magnet","ATTRACTOR","+80 XP magnet range",3,4,"magnet_r",80),
    ("m_coin_gain","TREASURY","+15% coin gain on death",6,4,"coin_mult",0.15),
    ("m_start_hp","SURVIVOR","Start each run +40 HP",7,3,"bonus_hp",40),
]

def apply_meta_to_player(player,save):
    mupg=save.get("meta_upgrades",{})
    for m in META_UPGRADES:
        uid,_,_,_,_,key,per=m
        lvl=mupg.get(uid,0)
        if lvl==0: continue
        val=per*lvl
        if key=="max_hp": player.max_hp+=val; player.hp=min(player.max_hp,player.hp+val)
        elif key=="xp_mult": player.xp_mult=getattr(player,"xp_mult",1.0)+val
        elif key=="speed": player.speed+=val
        elif key=="dmg": player.dmg+=val
        elif key=="hp_regen": player.hp_regen+=val
        elif key=="magnet_r": player.magnet_r+=val
        elif key=="bonus_hp": player.hp=min(player.max_hp,player.hp+val)

# ═══════ SUPER TIER ════════════════════════════════════════════════════════════
SUPER_BRANCHES=[
    ("sb_body","BODY","Physical enhancement",20,(255,80,80)),
    ("sb_mind","MIND","Utility & XP upgrades",18,(80,180,255)),
    ("sb_shadow","SHADOW","Evasion & stealth",25,(160,80,255)),
    ("sb_forge","FORGE","Weapon enhancement",22,(255,160,60)),
    ("sb_chaos","CHAOS","Volatile power",30,(255,60,140)),
]
SUPER_UPGRADES=[
    ("su_max_hp","TITAN FLESH","+80 max HP, heal 60","sb_body",8,5,"body_hp"),
    ("su_thorns","THORNWALL","Contact reflects 25% dmg","sb_body",12,3,"body_thorns"),
    ("su_armor","IRON SKIN","Take 10% less damage","sb_body",15,4,"body_armor"),
    ("su_vampiric","VAMPIRIC","+8 HP stolen per kill","sb_body",18,3,"body_vamp"),
    ("su_xp_surge","XP SURGE","XP orbs worth +20%","sb_mind",8,5,"mind_xp"),
    ("su_haste","HASTE","+0.4 move speed","sb_mind",10,5,"mind_speed"),
    ("su_luck","FORTUNE","+8% upgrade luck","sb_mind",12,4,"mind_luck"),
    ("su_aura","DRAW AURA","+150 XP magnet range","sb_mind",8,4,"mind_magnet"),
    ("su_evasion","PHANTOM STEP","8% dodge/stack (max 20%)","sb_shadow",15,3,"shadow_evasion"),
    ("su_blink","VOID BLINK","30% teleport on hit","sb_shadow",18,1,"shadow_blink"),
    ("su_ghost","GHOST FORM","Extra +0.8s invuln on hit","sb_shadow",12,3,"shadow_invuln"),
    ("su_wdmg","MASTERWORK","+20% weapon damage","sb_forge",12,4,"forge_wdmg"),
    ("su_wspd","OVERCLOCKED","Weapon fires 15% faster","sb_forge",12,4,"forge_wspd"),
    ("su_multi","ECHO STRIKE","15% chance to fire twice","sb_forge",18,2,"forge_echo"),
    ("su_volatile","VOLATILE","Kills explode for 30% dmg","sb_chaos",15,3,"chaos_volatile"),
    ("su_frenzy","BLOOD FRENZY","Kill gives +10% dmg 4s","sb_chaos",18,3,"chaos_frenzy"),
    ("su_curse","DOOM MARK","Enemies take 10% more dmg","sb_chaos",20,2,"chaos_curse"),
]

def get_super_upgrades_available(save):
    unlocked=save.get("super_tier_unlocked",{})
    levels=save.get("super_tier_levels",{})
    return [su for su in SUPER_UPGRADES if unlocked.get(su[3],False) and levels.get(su[0],0)<su[5]]

# ═══════ STRUCTURES ════════════════════════════════════════════════════════════
STRUCTURE_DEFS=[
    {"id":"shrine_hp","name":"BLOOD SHRINE","desc":"Restores 80 HP. Seek when low on health.","color":(220,50,50),"shape":"diamond","radius":32,"reward":("heal",80),"interact_msg":"Restored 80 HP!"},
    {"id":"shrine_xp","name":"XP MONOLITH","desc":"Ancient obelisk grants 250 XP instantly.","color":(60,255,120),"shape":"obelisk","radius":28,"reward":("xp",250),"interact_msg":"Absorbed ancient XP!"},
    {"id":"armory","name":"WEAPON CACHE","desc":"Abandoned cache gives a random upgrade.","color":(255,160,60),"shape":"box","radius":30,"reward":("random_upgrade",None),"interact_msg":"Found upgrade!"},
    {"id":"shrine_speed","name":"WIND ALTAR","desc":"Blesses you with +0.8 move speed for the run.","color":(80,255,220),"shape":"circle","radius":26,"reward":("speed",0.8),"interact_msg":"Feels lighter on your feet!"},
    {"id":"coin_vault","name":"COIN VAULT","desc":"Hidden vault contains 12 SuperCoins.","color":COIN_C,"shape":"star","radius":28,"reward":("supercoins",12),"interact_msg":"SuperCoins collected!"},
    {"id":"relic_dmg","name":"ANCIENT RELIC","desc":"Dormant relic grants +25 damage for the run.","color":(200,80,255),"shape":"triangle","radius":28,"reward":("dmg",25),"interact_msg":"Power surges through you!"},
    {"id":"nova_totem","name":"NOVA TOTEM","desc":"Totem imbues you with the Nova Burst ability.","color":NOVA_C,"shape":"diamond","radius":28,"reward":("nova",None),"interact_msg":"Absorbed nova energy!"},
]

# ═══════ WORLD EVENTS ══════════════════════════════════════════════════════════
WORLD_EVENTS=[
    {"id":"ev_gold_rush","name":"GOLD RUSH","desc":"All XP orbs worth 3× for 20s!","color":COIN_C,"duration":FPS*20,"effect":"xp_triple"},
    {"id":"ev_bloodmoon","name":"BLOOD MOON","desc":"Enemies deal 2× dmg, drop 2× XP! 15s","color":(200,0,0),"duration":FPS*15,"effect":"bloodmoon"},
    {"id":"ev_surge","name":"POWER SURGE","desc":"Your damage is tripled for 10s!","color":(255,200,0),"duration":FPS*10,"effect":"dmg_triple"},
    {"id":"ev_swarm","name":"SWARM TIDE","desc":"Defeat 30 enemies in 20s for +400 XP!","color":(220,50,50),"duration":FPS*20,"effect":"swarm_challenge","goal":30},
    {"id":"ev_freeze","name":"TIME FRACTURE","desc":"All enemies frozen for 5s!","color":(120,200,255),"duration":FPS*5,"effect":"freeze"},
    {"id":"ev_coinfall","name":"COIN SHOWER","desc":"SuperCoins rain down for 15s!","color":COIN_C,"duration":FPS*15,"effect":"coinfall"},
]

# ═══════ HELPERS ═══════════════════════════════════════════════════════════════
def dist(a,b): return math.hypot(a[0]-b[0],a[1]-b[1])
def norm(dx,dy):
    d=math.hypot(dx,dy)
    return (dx/d,dy/d) if d else (0.0,0.0)
def dtxt(surf,text,font,col,cx,cy):
    s=font.render(str(text),True,col); surf.blit(s,s.get_rect(center=(cx,cy)))
def dtxt_left(surf,text,font,col,x,y):
    s=font.render(str(text),True,col); surf.blit(s,(x,y))
def hbar(surf,x,y,w,h,ratio,fg,bg=(60,0,0)):
    pygame.draw.rect(surf,bg,(x,y,w,h))
    pygame.draw.rect(surf,fg,(x,y,int(w*max(0,min(1,ratio))),h))
    pygame.draw.rect(surf,GRAY,(x,y,w,h),1)
def lerp_col(a,b,t): return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))
def angle_diff(a,b): return (a-b+math.pi)%math.tau-math.pi

# ═══════ PARTICLE ══════════════════════════════════════════════════════════════
class Particle:
    __slots__=("x","y","vx","vy","life","ml","col","sz")
    def __init__(self,x,y,col,spd=3,sz=4,life=30):
        a=random.uniform(0,math.tau); s=random.uniform(.3,1.)*spd
        self.x,self.y=x,y; self.vx,self.vy=math.cos(a)*s,math.sin(a)*s
        self.life=self.ml=life; self.col=col; self.sz=sz
    def update(self):
        self.x+=self.vx; self.y+=self.vy; self.vx*=.91; self.vy*=.91; self.life-=1
    def draw(self,surf):
        t=self.life/self.ml; r,g,b=self.col; sz=max(1,int(self.sz*t))
        pygame.draw.circle(surf,(int(r*t),int(g*t),int(b*t)),(int(self.x),int(self.y)),sz)

def burst(lst,x,y,col,n=12,spd=5,sz=5,life=30):
    for _ in range(n): lst.append(Particle(x,y,col,spd,sz,life))

# ═══════ XP ORB ════════════════════════════════════════════════════════════════
class XPOrb:
    def __init__(self,x,y,val):
        self.x,self.y=x,y; self.val=val
        self.r=5+(val>=30)*2+(val>=100)*3+(val>=300)*2
        self.bob=random.uniform(0,math.tau); self.attr=False; self.alive=True
    def update(self,px,py,mag_r):
        self.bob+=.08; d=dist((self.x,self.y),(px,py))
        if d<mag_r or self.attr:
            self.attr=True; nx,ny=norm(px-self.x,py-self.y)
            sp=min(14,180/max(d,1)); self.x+=nx*sp; self.y+=ny*sp
    def draw(self,surf,ox,oy):
        sx=int(self.x-ox); sy=int(self.y-oy+math.sin(self.bob)*2)
        pygame.draw.circle(surf,XP_C,(sx,sy),self.r)
        pygame.draw.circle(surf,WHITE,(sx,sy),self.r,1)

class CoinParticle:
    def __init__(self,x,y):
        self.x=float(x); self.y=float(y)
        self.vy=random.uniform(-2,-4); self.vx=random.uniform(-1,1)
        self.life=self.ml=random.randint(80,130); self.r=random.randint(4,8); self.alive=True
    def update(self):
        self.y+=self.vy; self.x+=self.vx; self.vy+=0.05; self.life-=1
        if self.life<=0: self.alive=False
    def draw(self,surf,ox,oy):
        t=self.life/self.ml; sx,sy=int(self.x-ox),int(self.y-oy)
        r,g,b=COIN_C
        pygame.draw.circle(surf,(int(r*t),int(g*t),0),(sx,sy),max(1,int(self.r*t)))
        if t>0.5: pygame.draw.circle(surf,WHITE,(sx,sy),max(1,int(self.r*t)),1)

# ═══════ PROJECTILES ═══════════════════════════════════════════════════════════
class Bullet:
    def __init__(self,x,y,dx,dy,dmg,pierce=1,spd_m=1.0,col=BULLET_C,size=5,lifetime=65,enemy=False):
        nx,ny=norm(dx,dy); self.x,self.y=float(x),float(y)
        spd=14*spd_m; self.vx,self.vy=nx*spd,ny*spd
        self.dmg=dmg; self.pierce=pierce; self.life=lifetime
        self.hit=set(); self.col=col; self.sz=size; self.enemy=enemy
    def update(self): self.x+=self.vx; self.y+=self.vy; self.life-=1
    def draw(self,surf,ox,oy):
        sx,sy=int(self.x-ox),int(self.y-oy)
        for i in range(1,5):
            tx=int(self.x-self.vx*(i*.35)-ox); ty=int(self.y-self.vy*(i*.35)-oy)
            a=1-i/5; r,g,b=self.col
            pygame.draw.circle(surf,(int(r*a),int(g*a),int(b*a)),(tx,ty),max(1,self.sz-i))
        pygame.draw.circle(surf,self.col,(sx,sy),self.sz)
        pygame.draw.circle(surf,WHITE,(sx,sy),self.sz,1)
    @property
    def dead(self): return self.life<=0 or self.pierce<=0

class SniperBolt(Bullet):
    def __init__(self,x,y,dx,dy,dmg,enemy=False):
        super().__init__(x,y,dx,dy,dmg,pierce=99,spd_m=2.2,col=SNIPER_C,size=3,lifetime=60,enemy=enemy)

class PlasmaBall(Bullet):
    def __init__(self,x,y,dx,dy,dmg,explode_r=60,enemy=False):
        super().__init__(x,y,dx,dy,dmg,pierce=1,spd_m=.55,col=PLASMA_C,size=9,lifetime=90,enemy=enemy)
        self.explode_r=explode_r; self.exploded=False
    def explode(self,targets,particles):
        self.exploded=True; self.life=0
        burst(particles,self.x,self.y,PLASMA_C,n=20,spd=7,sz=6,life=35)
        for e in targets:
            d=dist((self.x,self.y),(e.x,e.y))
            if d<self.explode_r:
                falloff=1-d/self.explode_r
                e.take_damage(int(self.dmg*(.4+.6*falloff)))

class ChainBolt:
    SPEED=17; CHAIN_R=190
    def __init__(self,x,y,dx,dy,dmg,jumps,hit_ids=None):
        nx,ny=norm(dx,dy); self.x,self.y=float(x),float(y)
        self.vx,self.vy=nx*self.SPEED,ny*self.SPEED
        self.dmg=dmg; self.jumps=jumps; self.life=65
        self.hit=set(hit_ids) if hit_ids else set(); self.trail=[]; self.enemy=False
    def update(self):
        self.trail.append((self.x,self.y))
        if len(self.trail)>8: self.trail.pop(0)
        self.x+=self.vx; self.y+=self.vy; self.life-=1
    def draw(self,surf,ox,oy):
        for i,(tx,ty) in enumerate(self.trail):
            a=(i+1)/max(len(self.trail),1)
            jx=int(tx-ox+random.randint(-2,2)); jy=int(ty-oy+random.randint(-2,2))
            pygame.draw.circle(surf,(int(100*a),int(80*a),int(255*a)),(jx,jy),max(1,int(4*a)))
        pygame.draw.circle(surf,CHAIN_C,(int(self.x-ox),int(self.y-oy)),6)
        pygame.draw.circle(surf,WHITE,(int(self.x-ox),int(self.y-oy)),6,1)
    @property
    def dead(self): return self.life<=0

class TelegraphWarning:
    def __init__(self,x,y,wind_up,col=WARN_C,radius=28):
        self.x=x; self.y=y; self.wind_up=wind_up; self.timer=wind_up
        self.col=col; self.max_r=radius; self.alive=True
    def update(self):
        self.timer-=1
        if self.timer<=0: self.alive=False
    @property
    def progress(self): return 1-(self.timer/self.wind_up)
    def draw(self,surf,ox,oy):
        sx,sy=int(self.x-ox),int(self.y-oy); t=self.progress; r2=int(self.max_r*t)
        alpha_col=lerp_col((40,0,0),self.col,t); w=max(2,int(4*(1-t)+1))
        if r2>0: pygame.draw.circle(surf,alpha_col,(sx,sy),r2,w)
        if r2>3:
            r3,g3,b3=self.col
            pygame.draw.circle(surf,(int(r3*.15),int(g3*.15),int(b3*.15)),(sx,sy),r2-2)
        for i in range(4):
            a2=math.tau*i/4
            tx2=int(sx+math.cos(a2)*(self.max_r+6)); ty2=int(sy+math.sin(a2)*(self.max_r+6))
            pygame.draw.circle(surf,alpha_col,(tx2,ty2),2)

class LightningArc:
    def __init__(self,x1,y1,x2,y2,life=12):
        self.x1,self.y1,self.x2,self.y2=x1,y1,x2,y2; self.life=self.ml=life
    def draw(self,surf,ox,oy):
        t=self.life/self.ml; col=lerp_col((40,20,80),LIGHTNING_C,t)
        sx1,sy1=int(self.x1-ox),int(self.y1-oy); sx2,sy2=int(self.x2-ox),int(self.y2-oy)
        pts=[(sx1,sy1)]
        for i in range(1,6):
            fi=i/6
            pts.append((int(sx1+(sx2-sx1)*fi+random.randint(-10,10)),int(sy1+(sy2-sy1)*fi+random.randint(-10,10))))
        pts.append((sx2,sy2))
        for i in range(len(pts)-1): pygame.draw.line(surf,col,pts[i],pts[i+1],max(1,int(3*t)))

class LightningWave:
    def __init__(self,x,y,dmg,max_r=500):
        self.x,self.y=x,y; self.r=0; self.max_r=max_r
        self.dmg=dmg; self.speed=9; self.hit=set(); self.alive=True
    def update(self,enemies,particles):
        self.r+=self.speed
        for e in enemies:
            eid=id(e)
            if eid in self.hit: continue
            if abs(dist((self.x,self.y),(e.x,e.y))-self.r)<self.speed+e.radius:
                falloff=max(0,1-dist((self.x,self.y),(e.x,e.y))/self.max_r)
                e.take_damage(int(self.dmg*(0.3+0.7*falloff))); self.hit.add(eid)
                burst(particles,e.x,e.y,LIGHTNING_C,n=6,spd=4,sz=3,life=18)
        if self.r>=self.max_r: self.alive=False
    def draw(self,surf,ox,oy):
        t=1-self.r/self.max_r
        pygame.draw.circle(surf,lerp_col((20,10,40),LIGHTNING_C,t),(int(self.x-ox),int(self.y-oy)),int(self.r),max(1,int(4*t)))

class NovaBurst:
    def __init__(self,x,y,dmg,max_r=260):
        self.x,self.y=x,y; self.r=0; self.max_r=max_r
        self.dmg=dmg; self.spd=8; self.hit=set(); self.alive=True
    def update(self,enemies,particles):
        self.r+=self.spd
        for e in enemies:
            eid=id(e)
            if eid in self.hit: continue
            if abs(dist((self.x,self.y),(e.x,e.y))-self.r)<self.spd+e.radius:
                e.take_damage(self.dmg); self.hit.add(eid)
                burst(particles,e.x,e.y,NOVA_C,n=8,spd=5,sz=4,life=20)
        if self.r>=self.max_r: self.alive=False
    def draw(self,surf,ox,oy):
        w=max(1,int(5*(1-self.r/self.max_r)))
        pygame.draw.circle(surf,NOVA_C,(int(self.x-ox),int(self.y-oy)),int(self.r),w)

# ═══════ ORBIT SAW ═════════════════════════════════════════════════════════════
class OrbitSaw:
    def __init__(self,idx,total,orbit_r=80,dmg=15,spd=.035):
        self.angle=(math.tau/max(total,1))*idx; self.spin=0.0
        self.orbit_r=orbit_r; self.dmg=dmg; self.spd=spd; self.hit_cd={}; self.radius=14
    def update(self):
        self.angle=(self.angle+self.spd)%math.tau; self.spin=(self.spin+.15)%math.tau
    def world_pos(self,px,py): return px+math.cos(self.angle)*self.orbit_r, py+math.sin(self.angle)*self.orbit_r
    def check_hits(self,enemies,px,py,particles):
        wx,wy=self.world_pos(px,py)
        for e in enemies:
            eid=id(e); cd=self.hit_cd.get(eid,0)
            if cd>0: self.hit_cd[eid]=cd-1; continue
            if dist((wx,wy),(e.x,e.y))<self.radius+e.radius:
                e.take_damage(self.dmg); self.hit_cd[eid]=20
                burst(particles,wx,wy,SAW_C,n=5,spd=4,sz=3,life=15)
    def draw(self,surf,px,py,ox,oy):
        wx,wy=self.world_pos(px,py); sx,sy=int(wx-ox),int(wy-oy)
        for i in range(6):
            a=self.spin+(math.tau/6)*i
            pygame.draw.line(surf,SAW_C,(sx,sy),(int(sx+math.cos(a)*self.radius),int(sy+math.sin(a)*self.radius)),2)
        pygame.draw.circle(surf,SAW_C,(sx,sy),self.radius,2)
        pygame.draw.circle(surf,(180,210,255),(sx,sy),5)
        for i in range(1,5):
            ta=self.angle-i*.18; a2=1-i/5
            pygame.draw.circle(surf,(int(200*a2),int(230*a2),int(255*a2)),
                               (int(px+math.cos(ta)*self.orbit_r-ox),int(py+math.sin(ta)*self.orbit_r-oy)),max(1,int(3*a2)))

# ═══════ ENEMY ═════════════════════════════════════════════════════════════════
ENEMY_DEFS={
    "basic":(40,(1.2,2.0),14,10,10,ENEMY_C),
    "fast":(20,(3.2,4.8),10,6,14,(255,100,180)),
    "tank":(240,(0.6,1.0),26,22,40,ELITE_C),
    "brute":(130,(1.8,2.6),20,16,28,(200,90,20)),
    "ghost":(35,(2.0,2.9),12,8,20,(160,200,255)),
    "shielder":(80,(1.0,1.6),18,12,30,(100,180,100)),
    "spitter":(60,(1.4,2.0),15,6,32,(180,80,200)),
    "bomber":(50,(2.2,3.0),13,30,35,(255,60,60)),
    "armored":(350,(0.7,1.1),28,25,55,(120,140,160)),
    "swarm":(12,(3.5,5.5),8,5,8,(255,200,80)),
    "sniper_e":(55,(0.8,1.2),14,5,38,(255,180,80)),
    "mortar":(90,(0.5,0.9),18,8,45,(160,100,200)),
    "hexer":(70,(1.2,1.8),15,8,40,(80,200,255)),
    "boss_brute":(1600,(1.0,1.4),44,40,350,(220,50,50)),
    "boss_mage":(1400,(0.8,1.2),40,30,350,(120,60,255)),
    "boss_tank":(2800,(0.5,0.8),52,45,350,(100,120,140)),
    "megaboss":(5000,(0.7,1.0),58,55,800,(255,0,100)),
}

class Enemy:
    WIND_UP=55
    def __init__(self,x,y,etype="basic"):
        self.x,self.y=float(x),float(y); self.etype=etype
        self.flash=0; self.alive=True; self.frozen=0
        d=ENEMY_DEFS[etype]
        self.hp=self.max_hp=d[0]; self.speed=random.uniform(*d[1])
        self.radius=d[2]; self.contact_dmg=d[3]; self.xp=d[4]; self.color=d[5]
        self.shoot_cd=random.randint(60,180); self.wind_up_timer=0; self.winding_up=False
        self.exploded=False; self.phase=0; self.boss_cd=0
        self.charge_vx=self.charge_vy=0; self.charging=False; self.charge_timer=0

    @property
    def is_boss(self): return self.etype.startswith("boss_") or self.etype=="megaboss"
    @property
    def is_ranged(self): return self.etype in ("spitter","sniper_e","mortar","hexer")

    def in_fov(self,px,py):
        if not self.is_ranged: return False
        to_player=math.atan2(py-self.y,px-self.x)
        facing=getattr(self,"facing",to_player)
        return abs(angle_diff(to_player,facing))<RANGED_FOV

    def move_toward(self,px,py,freeze=False):
        if freeze or self.frozen>0: self.frozen=max(0,self.frozen-1); return
        if self.etype=="ghost" and random.random()<.003:
            a=random.uniform(0,math.tau); r=random.uniform(40,120)
            self.x+=math.cos(a)*r; self.y+=math.sin(a)*r; return
        if self.charging:
            self.x+=self.charge_vx; self.y+=self.charge_vy
            self.charge_timer-=1
            if self.charge_timer<=0: self.charging=False
            return
        dx,dy=px-self.x,py-self.y; nx,ny=norm(dx,dy)
        self.facing=math.atan2(ny,nx); self.x+=nx*self.speed; self.y+=ny*self.speed

    def take_damage(self,dmg,curse_bonus=0):
        if self.etype=="shielder" and random.random()<.3: dmg=max(1,dmg//3)
        if self.etype=="armored": dmg=max(1,int(dmg*0.5))
        if self.etype=="boss_tank" and self.phase==0: dmg=max(1,int(dmg*0.35))
        dmg=int(dmg*(1+curse_bonus)); self.hp-=dmg; self.flash=8
        if self.hp<=0: self.alive=False
        if self.is_boss and self.hp<self.max_hp*0.5 and self.phase==0:
            self.phase=1; self.speed*=1.4; self.flash=30

    def try_shoot(self,px,py,telegraph_list):
        if not self.is_ranged or not self.in_fov(px,py): return None
        if not self.winding_up:
            self.shoot_cd-=1
            if self.shoot_cd<=0:
                self.winding_up=True; self.wind_up_timer=0
                wind_col={"spitter":(180,80,200),"sniper_e":SNIPER_C,"mortar":(160,100,200),"hexer":(80,200,255)}.get(self.etype,WARN_C)
                telegraph_list.append(TelegraphWarning(self.x,self.y,self.WIND_UP,wind_col))
            return None
        else:
            self.wind_up_timer+=1
            if self.wind_up_timer>=self.WIND_UP:
                self.winding_up=False
                self.shoot_cd=random.randint(*({"spitter":(90,150),"sniper_e":(160,240),"mortar":(180,260),"hexer":(110,170)}.get(self.etype,(100,160))))
                return self._make_projectile(px,py)
            return None

    def _make_projectile(self,px,py):
        dx,dy=px-self.x,py-self.y
        if self.etype=="spitter":
            return Bullet(self.x,self.y,dx,dy,dmg=12,pierce=1,spd_m=.65,col=(200,80,220),size=8,lifetime=90,enemy=True)
        elif self.etype=="sniper_e":
            return SniperBolt(self.x,self.y,dx,dy,dmg=25,enemy=True)
        elif self.etype=="mortar":
            return Bullet(self.x,self.y,dx+random.uniform(-0.3,0.3),dy+random.uniform(-0.3,0.3),dmg=20,pierce=1,spd_m=.42,col=(180,100,220),size=11,lifetime=110,enemy=True)
        elif self.etype=="hexer":
            return ("hexer_volley",self.x,self.y,dx,dy)
        return None

    def try_boss_action(self,px,py,bullets,particles,telegraph_list):
        if not self.is_boss: return []
        self.boss_cd-=1
        if self.boss_cd>0: return []
        result=[]
        if self.etype=="boss_brute":
            if self.phase==0 or random.random()<0.5:
                dx,dy=norm(px-self.x,py-self.y)
                self.charge_vx=dx*12; self.charge_vy=dy*12; self.charging=True; self.charge_timer=18; self.boss_cd=FPS*3
            else:
                for i in range(8):
                    a=(math.tau/8)*i
                    result.append(Bullet(self.x,self.y,math.cos(a),math.sin(a),dmg=20,pierce=1,spd_m=.8,col=ELITE_C,size=8,lifetime=80,enemy=True))
                self.boss_cd=FPS*4; burst(particles,self.x,self.y,ELITE_C,n=20,spd=6,sz=5,life=30)
        elif self.etype=="boss_mage":
            if random.random()<0.4:
                a=random.uniform(0,math.tau); self.x=px+math.cos(a)*220; self.y=py+math.sin(a)*220
                burst(particles,self.x,self.y,BOSS_C,n=16,spd=7,sz=5,life=30)
                for i in range(8):
                    a2=(math.tau/8)*i
                    result.append(Bullet(self.x,self.y,math.cos(a2),math.sin(a2),dmg=18,pierce=1,spd_m=.9,col=BOSS_C,size=7,lifetime=75,enemy=True))
                self.boss_cd=FPS*3
            else:
                dx,dy=norm(px-self.x,py-self.y); base=math.atan2(dy,dx)
                for off in [-0.25,0,0.25]:
                    a3=base+off
                    result.append(Bullet(self.x,self.y,math.cos(a3),math.sin(a3),dmg=22,pierce=1,spd_m=1.1,col=(160,80,255),size=7,lifetime=70,enemy=True))
                self.boss_cd=FPS*2
        elif self.etype=="boss_tank":
            for _ in range(5 if self.phase==1 else 3):
                ox2=random.uniform(-150,150); oy2=random.uniform(-150,150)
                dx,dy=norm((px+ox2)-self.x,(py+oy2)-self.y)
                result.append(Bullet(self.x,self.y,dx,dy,dmg=25,pierce=1,spd_m=.38,col=(160,100,200),size=13,lifetime=130,enemy=True))
            self.boss_cd=FPS*(2 if self.phase==1 else 3)
            burst(particles,self.x,self.y,(160,100,200),n=10,spd=3,sz=4,life=25)
        elif self.etype=="megaboss":
            pat=random.randint(0,3)
            if pat==0:
                for i in range(12):
                    a=(math.tau/12)*i
                    result.append(Bullet(self.x,self.y,math.cos(a),math.sin(a),dmg=22,pierce=1,spd_m=1.0,col=(255,60,100),size=9,lifetime=80,enemy=True))
            elif pat==1:
                dx2,dy2=norm(px-self.x,py-self.y); base=math.atan2(dy2,dx2)
                for off in [-0.3,0,0.3]:
                    a4=base+off
                    result.append(Bullet(self.x,self.y,math.cos(a4),math.sin(a4),dmg=30,pierce=2,spd_m=1.3,col=(255,0,100),size=8,lifetime=70,enemy=True))
            elif pat==2:
                dx3,dy3=norm(px-self.x,py-self.y)
                self.charge_vx=dx3*14; self.charge_vy=dy3*14; self.charging=True; self.charge_timer=20
            else:
                for i in range(16):
                    a5=(math.tau/16)*i+self.boss_cd*.05
                    result.append(Bullet(self.x,self.y,math.cos(a5),math.sin(a5),dmg=18,pierce=1,spd_m=.7,col=(200,0,80),size=7,lifetime=90,enemy=True))
            self.boss_cd=FPS*(2 if self.phase==1 else 3)
            burst(particles,self.x,self.y,(255,0,100),n=15,spd=6,sz=5,life=25)
        return result

    def draw(self,surf,ox,oy):
        sx,sy=int(self.x-ox),int(self.y-oy)
        col=FLASH_C if self.flash>0 else self.color; self.flash=max(0,self.flash-1)
        if self.frozen>0: col=lerp_col(col,(120,200,255),0.6)
        border=3 if self.is_boss else 2
        pygame.draw.circle(surf,col,(sx,sy),self.radius)
        pygame.draw.circle(surf,WHITE,(sx,sy),self.radius,border)
        if self.is_boss:
            for i in range(6):
                a=math.tau*i/6
                tx2=int(sx+math.cos(a)*(self.radius+8)); ty2=int(sy+math.sin(a)*(self.radius+8))
                pygame.draw.line(surf,self.color,(sx,sy),(tx2,ty2),2)
            bw=min(600,W-100); bx=W//2-bw//2; by=H-90
            pygame.draw.rect(surf,(40,0,40),(bx-2,by-2,bw+4,22),border_radius=4)
            pygame.draw.rect(surf,self.color,(bx,by,int(bw*max(0,self.hp/self.max_hp)),18),border_radius=3)
            pygame.draw.rect(surf,WHITE,(bx,by,bw,18),1,border_radius=3)
            dtxt(surf,f"{self.etype.replace('_',' ').upper()}  {max(0,self.hp)}/{self.max_hp}",font_xs,WHITE,W//2,by+9)
        elif self.etype in ("sniper_e","mortar","hexer","spitter"):
            pygame.draw.line(surf,(255,200,100),(sx-8,sy),(sx+8,sy),2)
            pygame.draw.line(surf,(255,200,100),(sx,sy-8),(sx,sy+8),2)
        elif self.etype=="ghost":
            for bx2 in [-6,6]:
                pygame.draw.line(surf,(50,50,90),(sx+bx2-3,sy-7),(sx+bx2+3,sy-3),2)
                pygame.draw.line(surf,(50,50,90),(sx+bx2+3,sy-7),(sx+bx2-3,sy-3),2)
        elif self.etype=="bomber":
            t2=(pygame.time.get_ticks()%500)/500
            pygame.draw.circle(surf,(int(100+155*t2),int((100+155*t2)//2),0),(sx,sy),6)
        elif self.etype=="shielder":
            pygame.draw.arc(surf,(80,200,80),(sx-self.radius-4,sy-self.radius-4,(self.radius+4)*2,(self.radius+4)*2),-1,1,3)
        elif self.etype=="armored":
            pygame.draw.circle(surf,(80,100,120),(sx,sy),self.radius-5,4)
        else:
            eo=self.radius//3
            pygame.draw.circle(surf,(10,10,18),(sx-eo,sy-eo//2),3)
            pygame.draw.circle(surf,(10,10,18),(sx+eo,sy-eo//2),3)
        bw2=self.radius*2+4
        hbar(surf,sx-bw2//2,sy-self.radius-10,bw2,5,self.hp/self.max_hp,HP_FG)

# ═══════ WEAPONS ═══════════════════════════════════════════════════════════════
# Weapons declare which "universal" upgrades they accept
WEAPON_ALLOWED_UNIVERSAL={
    "pistol":   {"firerate","pierce","velocity"},
    "sword":    set(),                        # no universal gun upgrades
    "raygun":   {"firerate"},                 # beam has no pierce/velocity
    "lightning":{"firerate"},                 # range-based, no pierce/velocity
    "shotgun":  {"firerate","pierce"},        # no velocity (close-range feel)
    "plasma":   {"firerate"},                 # no pierce/velocity
    "sniper":   {"firerate","pierce"},        # no velocity (already super fast)
}

class Weapon:
    name="weapon"; color=WHITE
    RANGE=99999  # max targeting range, override per weapon
    def __init__(self):
        self.shoot_cd=0; self.special_cd=0; self.upgrades={}
    def has(self,uid,n=1): return self.upgrades.get(uid,0)>=n
    def count(self,uid): return self.upgrades.get(uid,0)
    def tick(self):
        self.shoot_cd=max(0,self.shoot_cd-1)
        self.special_cd=max(0,self.special_cd-1)
    def filter_enemies(self,px,py,enemies):
        """Return enemies within weapon range."""
        return [e for e in enemies if dist((px,py),(e.x,e.y))<=self.RANGE]
    def shoot(self,px,py,enemies,pdmg): return []
    def special(self,px,py,enemies,pdmg): return []
    def draw_held(self,surf,cx,cy,angle):
        ex=int(cx+math.cos(angle)*26); ey=int(cy+math.sin(angle)*26)
        pygame.draw.line(surf,self.color,(cx,cy),(ex,ey),5)
        pygame.draw.circle(surf,self.color,(ex,ey),5)
    def draw_range(self,surf,cx,cy): pass  # override for range-limited weapons
    def special_label(self): return "SPECIAL"

class Pistol(Weapon):
    name="pistol"; color=BULLET_C; RANGE=600
    def __init__(self): super().__init__()
    def shoot(self,px,py,enemies,pdmg):
        if self.shoot_cd>0: return []
        nearby=self.filter_enemies(px,py,enemies)
        if not nearby: return []
        target=min(nearby,key=lambda e:dist((px,py),(e.x,e.y)))
        dx,dy=target.x-px,target.y-py
        pierce=1+self.count("pierce"); spd_m=1+self.count("velocity")*.25
        n_shots=1+(2 if self.has("double") else 0)+(2 if self.has("triple") else 0)
        spread=0 if n_shots==1 else .18
        base_a=math.atan2(dy,dx); bullets=[]
        for i in range(n_shots):
            a=base_a+(i-(n_shots-1)/2)*spread
            if self.has("chain"):
                bullets.append(ChainBolt(px,py,math.cos(a),math.sin(a),pdmg,2+self.count("chain_up")*2))
            else:
                bullets.append(Bullet(px,py,math.cos(a),math.sin(a),pdmg,pierce,spd_m))
        self.shoot_cd=max(4,18-self.count("firerate")*3)
        return bullets
    def special(self,px,py,enemies,pdmg):
        if self.special_cd>0: return []
        nearby=self.filter_enemies(px,py,enemies)
        if not nearby: return []
        self.special_cd=FPS*5
        target=min(nearby,key=lambda e:dist((px,py),(e.x,e.y)))
        dx,dy=target.x-px,target.y-py
        return [Bullet(px,py,dx+random.uniform(-.3,.3),dy+random.uniform(-.3,.3),pdmg*2,1,1.3) for _ in range(5+self.count("burst_up")*2)]
    def special_label(self): return "BURST [Q]"

class Sword(Weapon):
    name="sword"; color=SWORD_C; RANGE=200  # melee only, enemies within 200 are "valid"
    def __init__(self):
        super().__init__(); self.shoot_cd=22; self.special_cd=0
        self.slash_arc=0; self.slash_timer=0
        # Parry state
        self.parry_cd=0; self.parrying=False; self.parry_timer=0
        self.PARRY_WINDOW=18   # frames parry is active
        self.PARRY_CD=FPS*2    # cooldown between parries
    def shoot(self,px,py,enemies,pdmg):
        if self.shoot_cd>0: return []
        nearby=self.filter_enemies(px,py,enemies)
        if not nearby: return []
        target=min(nearby,key=lambda e:dist((px,py),(e.x,e.y)))
        self.shoot_cd=max(8,22-self.count("fast")*4)
        range_r=70+self.count("range")*20; arc=math.pi*.6+self.count("wide")*.25
        base_a=math.atan2(target.y-py,target.x-px); dmg=pdmg+self.count("heavy")*15
        for e in nearby:
            ea=math.atan2(e.y-py,e.x-px)
            if abs(angle_diff(ea,base_a))<arc/2 and dist((px,py),(e.x,e.y))<range_r:
                e.take_damage(dmg)
        self.slash_arc=base_a; self.slash_timer=10; return []
    def try_parry(self,px,py):
        """Activate parry. Returns True if successfully started."""
        if self.parry_cd>0 or self.parrying: return False
        self.parrying=True; self.parry_timer=self.PARRY_WINDOW; return True
    def update_parry(self):
        if self.parry_cd>0: self.parry_cd-=1
        if self.parrying:
            self.parry_timer-=1
            if self.parry_timer<=0:
                self.parrying=False; self.parry_cd=self.PARRY_CD
    def check_parry_bullet(self,bx,by,px,py,particles):
        """Check if a bullet is within parry range. Returns parried dmg or 0."""
        if not self.parrying: return 0
        if dist((bx,by),(px,py))<45+self.count("parry_range")*10:
            burst(particles,bx,by,PARRY_C,n=10,spd=6,sz=4,life=20)
            return 1  # signal: parried
        return 0
    def special(self,px,py,enemies,pdmg):
        if self.special_cd>0: return []
        self.special_cd=max(FPS*2,(FPS*4)-self.count("dash_cd")*FPS)
        if enemies:
            target=min(enemies,key=lambda e:dist((px,py),(e.x,e.y)))
            dx,dy=norm(target.x-px,target.y-py)
        else:
            dx,dy=math.cos(0),math.sin(0)
        return [("sword_dash",(dx,dy,pdmg+self.count("dash_dmg")*20,8+self.count("dash_range")*4))]
    def special_label(self): return "DASH  [Q]"
    def draw_held(self,surf,cx,cy,angle):
        for w in [5,3]:
            pygame.draw.line(surf,SWORD_C if w==5 else WHITE,(cx,cy),(int(cx+math.cos(angle)*40),int(cy+math.sin(angle)*40)),w)
        if self.slash_timer>0:
            self.slash_timer-=1
            r2=70+self.count("range")*20; aw=.6+self.count("wide")*.25; t=self.slash_timer/10
            for i in range(12):
                a2=self.slash_arc-aw/2+(i/12)*aw; r3,g3,b3=SWORD_C
                pygame.draw.line(surf,(int(r3*t),int(g3*t),int(b3*t)),(cx,cy),(int(cx+math.cos(a2)*r2),int(cy+math.sin(a2)*r2)),2)
        if self.parrying:
            t=self.parry_timer/self.PARRY_WINDOW
            pr=45+self.count("parry_range")*10
            s2=pygame.Surface((pr*2+4,pr*2+4),pygame.SRCALPHA)
            pygame.draw.circle(s2,(int(180*t),int(255*t),int(80*t),int(80*t)),(pr+2,pr+2),pr)
            pygame.draw.circle(s2,(int(180*t),int(255*t),int(80*t),int(200*t)),(pr+2,pr+2),pr,3)
            surf.blit(s2,(cx-pr-2,cy-pr-2))

class Raygun(Weapon):
    name="raygun"; color=RAY_C; RANGE=700
    MODES=["closest","highest_hp","lowest_hp"]
    def __init__(self):
        super().__init__(); self.shoot_cd=0; self.special_cd=0
        self.mode_idx=0; self.locked_target=None; self.lock_dmg=1.0; self.beam_timer=0
    def _pick(self,px,py,enemies):
        if not enemies: return None
        m=self.MODES[self.mode_idx]
        if m=="closest": return min(enemies,key=lambda e:dist((px,py),(e.x,e.y)))
        if m=="highest_hp": return max(enemies,key=lambda e:e.hp)
        return min(enemies,key=lambda e:e.hp)
    def shoot(self,px,py,enemies,pdmg):
        if self.shoot_cd>0: return []
        nearby=self.filter_enemies(px,py,enemies)
        if not nearby: return []
        if self.locked_target and (not self.locked_target.alive or self.locked_target not in nearby):
            self.locked_target=None; self.lock_dmg=1.0
        if not self.locked_target: self.locked_target=self._pick(px,py,nearby); self.lock_dmg=1.0
        e=self.locked_target
        if e not in nearby: self.locked_target=None; return []
        self.lock_dmg=min(4.0+self.count("ramp")*.5,self.lock_dmg+.06)
        dmg=int(pdmg*.6*self.lock_dmg)+self.count("base_dmg")*8
        self.shoot_cd=max(3,10-self.count("firerate")*2)
        self.beam_timer=8; e.take_damage(dmg)
        if self.has("bounce"):
            others=[x for x in nearby if x is not e]
            for _ in range(self.count("bounce")):
                if not others: break
                t2=min(others,key=lambda x:dist((e.x,e.y),(x.x,x.y)))
                t2.take_damage(max(1,dmg//2)); others.remove(t2)
        return []
    def special(self,px,py,enemies,pdmg):
        if self.special_cd>0: return []
        self.special_cd=FPS*3; self.locked_target=None; self.lock_dmg=1.0
        self.mode_idx=(self.mode_idx+1)%len(self.MODES)
        return [("raygun_mode",None)]
    def special_label(self): return f"MODE:{self.MODES[self.mode_idx][:3].upper()} [Q]"
    def draw_held(self,surf,cx,cy,angle):
        ex=int(cx+math.cos(angle)*26); ey=int(cy+math.sin(angle)*26)
        pygame.draw.line(surf,RAY_C,(cx,cy),(ex,ey),7)
        pygame.draw.circle(surf,RAY_C,(ex,ey),7); pygame.draw.circle(surf,WHITE,(ex,ey),7,1)

class LightningGun(Weapon):
    name="lightning"; color=LIGHTNING_C
    BASE_RANGE=280  # lightning range shown as a circle
    def __init__(self): super().__init__(); self.shoot_cd=0; self.special_cd=0
    @property
    def RANGE(self): return self.BASE_RANGE+self.count("range_up")*40
    def shoot(self,px,py,enemies,pdmg):
        if self.shoot_cd>0: return []
        nearby=self.filter_enemies(px,py,enemies)
        if not nearby: return []
        n=2+self.count("multistrike")*2
        targets=sorted(nearby,key=lambda e:dist((px,py),(e.x,e.y)))[:n]
        dmg=pdmg+self.count("dmg")*10
        for e in targets: e.take_damage(dmg)
        self.shoot_cd=max(8,25-self.count("firerate")*4)
        return [(("lightning_arc",((px,py),(e.x,e.y)))) for e in targets]
    def special(self,px,py,enemies,pdmg):
        if self.special_cd>0: return []
        self.special_cd=FPS*(6-self.count("wave_cd"))
        return [("lightning_wave",LightningWave(px,py,pdmg*2+self.count("wave_dmg")*15,450+self.count("wave_range")*80))]
    def special_label(self): return "WAVE  [Q]"
    def draw_range(self,surf,cx,cy):
        """Draw translucent range circle around player."""
        r=self.RANGE
        s=pygame.Surface((r*2+4,r*2+4),pygame.SRCALPHA)
        pygame.draw.circle(s,(200,160,255,18),(r+2,r+2),r)
        pygame.draw.circle(s,(200,160,255,70),(r+2,r+2),r,2)
        surf.blit(s,(cx-r-2,cy-r-2))

class Shotgun(Weapon):
    name="shotgun"; color=SHOTGUN_C; RANGE=350
    def __init__(self): super().__init__()
    def shoot(self,px,py,enemies,pdmg):
        if self.shoot_cd>0: return []
        nearby=self.filter_enemies(px,py,enemies)
        if not nearby: return []
        target=min(nearby,key=lambda e:dist((px,py),(e.x,e.y)))
        base_a=math.atan2(target.y-py,target.x-px)
        pellets=5+self.count("pellets")*2; dmg=pdmg+self.count("dmg")*8; bullets=[]
        for _ in range(pellets):
            a=base_a+random.uniform(-1,1)*(.45+self.count("spread")*.1)
            bullets.append(Bullet(px,py,math.cos(a),math.sin(a),dmg,1+self.count("pierce"),.95,SHOTGUN_C,5))
        self.shoot_cd=max(20,50-self.count("firerate")*6)
        return bullets
    def special(self,px,py,enemies,pdmg):
        if self.special_cd>0: return []
        self.special_cd=FPS*(5-self.count("slam_cd"))
        n=12+self.count("slam_count")*4
        return [Bullet(px,py,math.cos((math.tau/n)*i),math.sin((math.tau/n)*i),pdmg*3,1,1.0,SHOTGUN_C,7) for i in range(n)]
    def special_label(self): return "360°  [Q]"

class PlasmaLauncher(Weapon):
    name="plasma"; color=PLASMA_C; RANGE=550
    def __init__(self): super().__init__()
    def shoot(self,px,py,enemies,pdmg):
        if self.shoot_cd>0: return []
        nearby=self.filter_enemies(px,py,enemies)
        if not nearby: return []
        target=min(nearby,key=lambda e:dist((px,py),(e.x,e.y)))
        dx,dy=target.x-px,target.y-py
        b=PlasmaBall(px,py,dx,dy,pdmg+self.count("dmg")*12,60+self.count("explode_r")*15)
        self.shoot_cd=max(25,55-self.count("firerate")*7)
        return [b]
    def special(self,px,py,enemies,pdmg):
        if self.special_cd>0 or not enemies: return []
        self.special_cd=FPS*(7-self.count("volley_cd"))
        nearby=self.filter_enemies(px,py,enemies)
        targets=sorted(nearby,key=lambda e:dist((px,py),(e.x,e.y)))[:3+self.count("volley_count")]
        return [PlasmaBall(px,py,t.x-px,t.y-py,pdmg,60) for t in targets]
    def special_label(self): return "VOLLEY[Q]"

class SniperRifle(Weapon):
    name="sniper"; color=SNIPER_C; RANGE=9999  # infinite - targets farthest
    def __init__(self): super().__init__()
    def shoot(self,px,py,enemies,pdmg):
        if self.shoot_cd>0 or not enemies: return []
        target=max(enemies,key=lambda e:dist((px,py),(e.x,e.y)))
        dx,dy=target.x-px,target.y-py
        base_a=math.atan2(dy,dx); n=1+self.count("multi"); bullets=[]
        for i in range(n):
            a=base_a+(i-(n-1)/2)*.08
            bullets.append(SniperBolt(px,py,math.cos(a),math.sin(a),(pdmg*3)+self.count("dmg")*25))
        self.shoot_cd=max(25,60-self.count("firerate")*8)
        return bullets
    def special(self,px,py,enemies,pdmg):
        if self.special_cd>0: return []
        self.special_cd=FPS*(8-self.count("mark_cd"))
        return [("sniper_mark",enemies[:])]
    def special_label(self): return "MARK  [Q]"

WEAPON_CLASSES={"pistol":Pistol,"sword":Sword,"raygun":Raygun,
                "lightning":LightningGun,"shotgun":Shotgun,
                "plasma":PlasmaLauncher,"sniper":SniperRifle}
def make_weapon(wtype): return WEAPON_CLASSES[wtype]()

# ═══════ PLAYER ════════════════════════════════════════════════════════════════
class Player:
    def __init__(self,starting_weapon="pistol"):
        self.x=self.y=0.0; self.hp=self.max_hp=120
        self.xp=0; self.level=1; self.xp_next=100
        self.invincible=0; self.radius=16; self.angle=0.0
        self.speed=4.5; self.dmg=20; self.hp_regen=0; self.regen_t=0
        self.magnet_r=120; self.xp_mult=1.0
        self.num_saws=0; self.saws=[]
        self.has_nova=False; self.nova_cd=0; self.nova_interval=FPS*8
        self.weapon=make_weapon(starting_weapon)
        self.dashing=False; self.dash_vx=0; self.dash_vy=0
        self.dash_frames=0; self.dash_dmg=0; self.dash_hit=set()
        self.marked_enemies=set(); self.mark_timer=0
        # super tier
        self.evasion_chance=0.0; self.armor_pct=0.0; self.thorns_pct=0.0
        self.vamp_per_kill=0; self.void_blink=False; self.extra_invuln=0
        self.wdmg_mult=1.0; self.wspd_mult=1.0; self.echo_chance=0.0
        self.volatile_pct=0.0; self.frenzy_stacks=0; self.curse_bonus=0.0
        self.luck_bonus=0.0; self.dmg_bonus_temp=0.0; self.dmg_bonus_timer=0

    def rebuild_saws(self):
        n=self.num_saws
        self.saws=[OrbitSaw(i,n,orbit_r=80+n*8,dmg=12+n*3,spd=.035+n*.003) for i in range(n)]

    def apply_super(self,effect_key,save):
        lvl=save.get("super_tier_levels",{}).get(next((s[0] for s in SUPER_UPGRADES if s[6]==effect_key),""),0)
        if effect_key=="body_hp": self.max_hp+=80*lvl; self.hp=min(self.max_hp,self.hp+60)
        elif effect_key=="body_thorns": self.thorns_pct=min(0.5,0.25*lvl)
        elif effect_key=="body_armor": self.armor_pct=min(0.4,0.10*lvl)
        elif effect_key=="body_vamp": self.vamp_per_kill=8*lvl
        elif effect_key=="mind_xp": self.xp_mult+=0.2*lvl
        elif effect_key=="mind_speed": self.speed+=0.4*lvl
        elif effect_key=="mind_luck": self.luck_bonus=0.08*lvl
        elif effect_key=="mind_magnet": self.magnet_r+=150*lvl
        elif effect_key=="shadow_evasion": self.evasion_chance=min(0.20,0.08*lvl)
        elif effect_key=="shadow_blink": self.void_blink=True
        elif effect_key=="shadow_invuln": self.extra_invuln=int(FPS*0.8*lvl)
        elif effect_key=="forge_wdmg": self.wdmg_mult=1.0+0.20*lvl
        elif effect_key=="forge_wspd": self.wspd_mult=1.0-0.15*lvl
        elif effect_key=="forge_echo": self.echo_chance=0.15*lvl
        elif effect_key=="chaos_volatile": self.volatile_pct=0.30*lvl
        elif effect_key=="chaos_frenzy": self.frenzy_stacks=lvl
        elif effect_key=="chaos_curse": self.curse_bonus=0.10*lvl

    def move(self,keys):
        if self.dashing:
            self.x+=self.dash_vx; self.y+=self.dash_vy; self.dash_frames-=1
            if self.dash_frames<=0: self.dashing=False; return
        dx=dy=0
        if keys[pygame.K_w] or keys[pygame.K_UP]: dy-=1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: dy+=1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: dx-=1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx+=1
        if dx or dy:
            nx,ny=norm(dx,dy); self.x+=nx*self.speed; self.y+=ny*self.speed
            self.angle=math.atan2(ny,nx)

    def start_dash(self,vx,vy,dmg,frames):
        nx,ny=norm(vx,vy); self.dash_vx=nx*10; self.dash_vy=ny*10
        self.dash_dmg=dmg; self.dash_frames=frames
        self.dashing=True; self.invincible=frames+10; self.dash_hit=set()

    def update(self,enemies,particles):
        self.invincible=max(0,self.invincible-1)
        self.weapon.tick()
        if hasattr(self.weapon,"update_parry"): self.weapon.update_parry()
        for saw in self.saws: saw.update()
        if self.has_nova: self.nova_cd=max(0,self.nova_cd-1)
        if self.hp_regen>0:
            self.regen_t+=1
            if self.regen_t>=FPS: self.regen_t=0; self.hp=min(self.max_hp,self.hp+self.hp_regen)
        if self.mark_timer>0: self.mark_timer-=1
        else: self.marked_enemies.clear()
        if self.dmg_bonus_timer>0:
            self.dmg_bonus_timer-=1
            if self.dmg_bonus_timer<=0: self.dmg_bonus_temp=0.0
        if self.dashing:
            for e in enemies:
                eid=id(e)
                if eid in self.dash_hit: continue
                if dist((self.x,self.y),(e.x,e.y))<self.radius+e.radius+8:
                    e.take_damage(self.dash_dmg); self.dash_hit.add(eid)
                    burst(particles,e.x,e.y,SWORD_C,n=8,spd=5,sz=4,life=20)

    def on_kill(self,enemy,particles,enemies_list):
        if self.vamp_per_kill>0: self.hp=min(self.max_hp,self.hp+self.vamp_per_kill)
        if self.volatile_pct>0:
            vdmg=int(enemy.max_hp*self.volatile_pct)
            for e in enemies_list:
                if dist((enemy.x,enemy.y),(e.x,e.y))<60: e.take_damage(vdmg)
            burst(particles,enemy.x,enemy.y,(255,100,50),n=12,spd=6,sz=4,life=22)
        if self.frenzy_stacks>0:
            self.dmg_bonus_temp=0.10*self.frenzy_stacks; self.dmg_bonus_timer=FPS*4

    def effective_dmg(self):
        return int(self.dmg*self.wdmg_mult*(1+self.dmg_bonus_temp))

    def gain_xp(self,v):
        v2=int(v*self.xp_mult); self.xp+=v2; lv=False
        while self.xp>=self.xp_next:
            self.xp-=self.xp_next; self.level+=1; self.xp_next=int(self.xp_next*1.30); lv=True
        return lv

    def take_damage(self,dmg):
        if self.invincible>0 or self.dashing: return False
        if self.evasion_chance>0 and random.random()<self.evasion_chance: return False  # dodged
        if self.armor_pct>0: dmg=max(1,int(dmg*(1-self.armor_pct)))
        self.hp-=dmg; self.invincible=45+self.extra_invuln
        if self.void_blink and random.random()<0.30:
            a=random.uniform(0,math.tau); self.x+=math.cos(a)*120; self.y+=math.sin(a)*120
        return True  # was hit

    def thorns_dmg(self,attacker_dmg):
        return int(attacker_dmg*self.thorns_pct) if self.thorns_pct>0 else 0

    def draw(self,surf):
        cx,cy=W//2,H//2
        if self.invincible>0 and (self.invincible//4)%2==0: return
        # weapon range indicator (lightning)
        self.weapon.draw_range(surf,cx,cy)
        if self.dashing:
            for i in range(3):
                a=1-i/3; r2,g2,b2=SWORD_C
                pygame.draw.circle(surf,(int(r2*a),int(g2*a),int(b2*a)),
                                   (int(cx-self.dash_vx*i*1.5),int(cy-self.dash_vy*i*1.5)),int(self.radius*(1-i*.2)))
        if self.dmg_bonus_timer>0:
            t=self.dmg_bonus_timer/(FPS*4)
            pygame.draw.circle(surf,(int(255*t),int(80*t),0),(cx,cy),self.radius+6,2)
        pygame.draw.circle(surf,PLAYER_C,(cx,cy),self.radius)
        pygame.draw.circle(surf,WHITE,(cx,cy),self.radius,2)
        self.weapon.draw_held(surf,cx,cy,self.angle)

# ═══════ UPGRADE SYSTEM ════════════════════════════════════════════════════════
def _saw_dmg(p,v):
    for s in p.saws: s.dmg+=v

def _upg(uid,name,desc,col,cat,weapon,ms,req,fn,exclude_weapons=None):
    return {"id":uid,"name":name,"desc":desc,"color":col,"cat":cat,
            "weapon":weapon,"max_stack":ms,"requires":req,"apply":fn,
            "super":False,"exclude_weapons":exclude_weapons or []}

UPGRADE_LIST=[
    # ─── CHARACTER ───────────────────────────────────────────────────────────
    _upg("max_hp","IRON FLESH","+70 max HP & heal",(220,50,50),"char",None,None,None,
         lambda p:(setattr(p,"max_hp",p.max_hp+70),setattr(p,"hp",min(p.max_hp+70,p.hp+70)))),
    _upg("regen","BLOODLEECH","+3 HP regen/s",(255,80,120),"char",None,6,None,
         lambda p:setattr(p,"hp_regen",p.hp_regen+3)),
    _upg("speed","FLEET FOOT","+0.6 move speed",(80,255,200),"char",None,5,None,
         lambda p:setattr(p,"speed",round(p.speed+.6,2))),
    _upg("magnet","XP MAGNET","XP draws from farther",(60,180,255),"char",None,3,None,
         lambda p:setattr(p,"magnet_r",p.magnet_r+130)),
    _upg("medkit","MEDKIT","Restore 60 HP",(200,255,200),"char",None,None,None,
         lambda p:setattr(p,"hp",min(p.max_hp,p.hp+60))),
    _upg("global_dmg","POWER CORE","+15 base damage",(255,200,80),"char",None,None,None,
         lambda p:setattr(p,"dmg",p.dmg+15)),
    _upg("saw_1","SAW ORBIT","Orbiting saw blade\nspins around you",(200,230,255),"char",None,1,None,
         lambda p:(setattr(p,"num_saws",1),p.rebuild_saws())),
    _upg("saw_more","MORE SAWS","+1 orbiting saw",(200,230,255),"char",None,5,"saw_1",
         lambda p:(setattr(p,"num_saws",p.num_saws+1),p.rebuild_saws())),
    _upg("saw_dmg","SAW SHARPENED","Saws +18 damage",(200,230,255),"char",None,None,"saw_1",
         lambda p:_saw_dmg(p,18)),
    _upg("nova","NOVA BURST","Energy ring every 8s\ndamages all nearby",(255,200,60),"char",None,1,None,
         lambda p:(setattr(p,"has_nova",True),setattr(p,"nova_cd",p.nova_interval))),
    _upg("nova_cd","NOVA CHARGED","Nova 2s more often",(255,200,60),"char",None,3,"nova",
         lambda p:setattr(p,"nova_interval",max(FPS*2,p.nova_interval-FPS*2))),

    # ─── UNIVERSAL GUN (weapon-filtered) ─────────────────────────────────────
    # Firerate: all weapons get it via their own specific upgrades or this
    # Pierce: projectile weapons only (not lightning, sword, raygun lock)
    # Velocity: projectile weapons only (not lightning/raygun/sword)
    _upg("u_firerate","RAPID FIRE","Fire 4 frames faster",BULLET_C,"gun",None,6,None,
         lambda p:p.weapon.upgrades.update({"firerate":p.weapon.count("firerate")+1}),
         exclude_weapons=["sword"]),  # sword has its own fast upgrade
    _upg("u_pierce","PIERCING","Bullets pierce +1",(255,200,80),"gun",None,5,None,
         lambda p:p.weapon.upgrades.update({"pierce":p.weapon.count("pierce")+1}),
         exclude_weapons=["sword","raygun","lightning","plasma"]),
    _upg("u_velocity","VELOCITY","Bullets 25% faster",(255,230,100),"gun",None,4,None,
         lambda p:p.weapon.upgrades.update({"velocity":p.weapon.count("velocity")+1}),
         exclude_weapons=["sword","raygun","lightning","plasma","sniper"]),

    # ─── PISTOL ──────────────────────────────────────────────────────────────
    _upg("p_double","DOUBLE SHOT","Fire 2 extra bullets",BULLET_C,"gun","pistol",1,None,
         lambda p:p.weapon.upgrades.update({"double":1})),
    _upg("p_triple","TRIPLE SHOT","+2 more bullets\n(needs Double)",BULLET_C,"gun","pistol",1,"p_double",
         lambda p:p.weapon.upgrades.update({"triple":1})),
    _upg("p_chain","CHAIN BOLT","Shots arc to nearby\nenemies",(120,80,255),"gun","pistol",1,None,
         lambda p:p.weapon.upgrades.update({"chain":1})),
    _upg("p_chain_up","CHAIN+","+2 chain jumps",(120,80,255),"gun","pistol",4,"p_chain",
         lambda p:p.weapon.upgrades.update({"chain_up":p.weapon.count("chain_up")+1})),
    _upg("p_burst_up","BURST+","+2 shots in burst",BULLET_C,"gun","pistol",3,None,
         lambda p:p.weapon.upgrades.update({"burst_up":p.weapon.count("burst_up")+1})),

    # ─── SWORD ───────────────────────────────────────────────────────────────
    _upg("s_heavy","HEAVY BLADE","+15 slash damage",SWORD_C,"gun","sword",None,None,
         lambda p:p.weapon.upgrades.update({"heavy":p.weapon.count("heavy")+1})),
    _upg("s_range","LONG REACH","+20 slash range",SWORD_C,"gun","sword",4,None,
         lambda p:p.weapon.upgrades.update({"range":p.weapon.count("range")+1})),
    _upg("s_wide","WIDE ARC","Wider slash angle",(200,220,255),"gun","sword",3,None,
         lambda p:p.weapon.upgrades.update({"wide":p.weapon.count("wide")+1})),
    _upg("s_fast","SWIFT BLADE","Slash faster",SWORD_C,"gun","sword",4,None,
         lambda p:p.weapon.upgrades.update({"fast":p.weapon.count("fast")+1})),
    _upg("s_dash_dmg","DASH STRIKE","+20 dash damage",(180,200,255),"gun","sword",None,None,
         lambda p:p.weapon.upgrades.update({"dash_dmg":p.weapon.count("dash_dmg")+1})),
    _upg("s_dash_cd","SWIFT DASH","Dash CD -1s",(180,200,255),"gun","sword",2,None,
         lambda p:p.weapon.upgrades.update({"dash_cd":min(2,p.weapon.count("dash_cd")+1)})),
    _upg("s_parry","PARRY MASTER","+10 parry radius\n+instant counter",PARRY_C,"gun","sword",3,None,
         lambda p:p.weapon.upgrades.update({"parry_range":p.weapon.count("parry_range")+1})),

    # ─── RAYGUN ──────────────────────────────────────────────────────────────
    _upg("r_ramp","LOCK RAMP","Damage ramps higher\non sustained lock",RAY_C,"gun","raygun",4,None,
         lambda p:p.weapon.upgrades.update({"ramp":p.weapon.count("ramp")+1})),
    _upg("r_base","OVERCHARGE","+8 base ray damage",RAY_C,"gun","raygun",None,None,
         lambda p:p.weapon.upgrades.update({"base_dmg":p.weapon.count("base_dmg")+1})),
    _upg("r_bounce","BEAM BOUNCE","Beam bounces to\nnearby enemies",RAY_C,"gun","raygun",3,None,
         lambda p:p.weapon.upgrades.update({"bounce":p.weapon.count("bounce")+1})),
    _upg("r_firerate","RAPID RAY","Ray fires faster",RAY_C,"gun","raygun",4,None,
         lambda p:p.weapon.upgrades.update({"firerate":p.weapon.count("firerate")+1})),

    # ─── LIGHTNING ───────────────────────────────────────────────────────────
    _upg("l_multi","MULTISTRIKE","+2 simultaneous\ntargets",LIGHTNING_C,"gun","lightning",4,None,
         lambda p:p.weapon.upgrades.update({"multistrike":p.weapon.count("multistrike")+1})),
    _upg("l_dmg","SHOCK COIL","+10 lightning dmg",LIGHTNING_C,"gun","lightning",None,None,
         lambda p:p.weapon.upgrades.update({"dmg":p.weapon.count("dmg")+1})),
    _upg("l_range","EXTENDED ARC","+40 strike range",LIGHTNING_C,"gun","lightning",4,None,
         lambda p:p.weapon.upgrades.update({"range_up":p.weapon.count("range_up")+1})),
    _upg("l_wave_cd","OVERLOAD","Wave CD -1s",LIGHTNING_C,"gun","lightning",4,None,
         lambda p:p.weapon.upgrades.update({"wave_cd":min(4,p.weapon.count("wave_cd")+1)})),
    _upg("l_wave_dmg","SURGE WAVE","+15 wave damage",LIGHTNING_C,"gun","lightning",None,"l_wave_cd",
         lambda p:p.weapon.upgrades.update({"wave_dmg":p.weapon.count("wave_dmg")+1})),
    _upg("l_wave_r","WIDE WAVE","+80 wave radius",LIGHTNING_C,"gun","lightning",3,None,
         lambda p:p.weapon.upgrades.update({"wave_range":p.weapon.count("wave_range")+1})),

    # ─── SHOTGUN ─────────────────────────────────────────────────────────────
    _upg("sg_pellets","MORE PELLETS","+2 pellets per shot",SHOTGUN_C,"gun","shotgun",4,None,
         lambda p:p.weapon.upgrades.update({"pellets":p.weapon.count("pellets")+1})),
    _upg("sg_dmg","BUCKSHOT","+8 pellet damage",SHOTGUN_C,"gun","shotgun",None,None,
         lambda p:p.weapon.upgrades.update({"dmg":p.weapon.count("dmg")+1})),
    _upg("sg_slam_up","MEGA SLAM","+4 360° pellets",SHOTGUN_C,"gun","shotgun",3,None,
         lambda p:p.weapon.upgrades.update({"slam_count":p.weapon.count("slam_count")+1})),

    # ─── PLASMA ──────────────────────────────────────────────────────────────
    _upg("pl_explode","BIG BANG","+15 explosion radius",PLASMA_C,"gun","plasma",4,None,
         lambda p:p.weapon.upgrades.update({"explode_r":p.weapon.count("explode_r")+1})),
    _upg("pl_dmg","PLASMA CORE","+12 plasma damage",PLASMA_C,"gun","plasma",None,None,
         lambda p:p.weapon.upgrades.update({"dmg":p.weapon.count("dmg")+1})),
    _upg("pl_volley_up","VOLLEY+","+1 volley target",PLASMA_C,"gun","plasma",3,None,
         lambda p:p.weapon.upgrades.update({"volley_count":p.weapon.count("volley_count")+1})),

    # ─── SNIPER ──────────────────────────────────────────────────────────────
    _upg("sn_dmg","HOLLOW POINT","+25 sniper damage",SNIPER_C,"gun","sniper",None,None,
         lambda p:p.weapon.upgrades.update({"dmg":p.weapon.count("dmg")+1})),
    _upg("sn_multi","MULTI-SHOT","Fire 2 bolts at once",SNIPER_C,"gun","sniper",1,None,
         lambda p:p.weapon.upgrades.update({"multi":1})),
    _upg("sn_firerate","QUICK BOLT","Reload faster",SNIPER_C,"gun","sniper",4,None,
         lambda p:p.weapon.upgrades.update({"firerate":p.weapon.count("firerate")+1})),
    _upg("sn_mark_cd","HUNTER'S MARK","Reduce mark CD",SNIPER_C,"gun","sniper",3,None,
         lambda p:p.weapon.upgrades.update({"mark_cd":min(6,p.weapon.count("mark_cd")+1)})),
]

def make_super_upgrade_cards(save):
    avail=get_super_upgrades_available(save); cards=[]
    for su in avail:
        uid,name,desc,branch,cost,ms,eff=su
        def make_fn(ek,sv=save):
            def fn(p): p.apply_super(ek,sv)
            return fn
        cards.append({"id":uid,"name":"✦ "+name,"desc":desc,"color":SUPER_C,
                       "cat":"super","weapon":None,"max_stack":ms,"requires":None,
                       "apply":make_fn(eff),"super":True,"branch":branch,"exclude_weapons":[]})
    return cards

def _upg_ok(u,player,acquired):
    if u.get("super",False): return True
    wn=player.weapon.name
    if u["weapon"] and u["weapon"]!=wn: return False
    if wn in u.get("exclude_weapons",[]): return False
    req=u.get("requires")
    if req and acquired.get(req,0)<1: return False
    ms=u["max_stack"]
    if ms and acquired.get(u["id"],0)>=ms: return False
    return True

def pick_upgrades(player,acquired,save,n=3):
    pool=[u for u in UPGRADE_LIST if _upg_ok(u,player,acquired)]
    super_pool=make_super_upgrade_cards(save)
    for s in super_pool:
        if acquired.get(s["id"],0)<s["max_stack"]: pool.append(s)
    gun=[u for u in pool if u["cat"]=="gun"]
    char=[u for u in pool if u["cat"]=="char"]
    sup=[u for u in pool if u["cat"]=="super"]
    luck=getattr(player,"luck_bonus",0)
    random.shuffle(gun); random.shuffle(char); random.shuffle(sup)
    picks=[]
    if sup and random.random()<0.30+luck: picks.append(sup[0])
    pool2=gun+char; random.shuffle(pool2)
    for u in pool2:
        if len(picks)>=n: break
        if u not in picks: picks.append(u)
    rem=pool2+sup; random.shuffle(rem)
    while len(picks)<n and rem:
        u=rem.pop(0)
        if u not in picks: picks.append(u)
    return picks[:n]

# ═══════ WAVE MANAGER ══════════════════════════════════════════════════════════
SPAWN_TABLE={
    1:[("basic",10),("fast",3)],
    2:[("basic",8),("fast",5),("ghost",3)],
    3:[("basic",6),("fast",4),("ghost",3),("brute",3),("swarm",4),("spitter",2)],
    4:[("basic",5),("fast",4),("brute",4),("tank",2),("swarm",4),("spitter",3),("sniper_e",2)],
    5:[("basic",4),("fast",3),("brute",3),("tank",3),("swarm",4),("shielder",2),("spitter",3),("sniper_e",2),("hexer",2)],
    6:[("basic",3),("fast",3),("brute",3),("tank",3),("swarm",3),("shielder",3),("spitter",2),("sniper_e",3),("hexer",2),("mortar",2),("bomber",2)],
    7:[("basic",2),("fast",2),("brute",3),("tank",3),("swarm",3),("shielder",2),("spitter",2),("sniper_e",3),("hexer",3),("mortar",3),("bomber",2),("armored",2)],
    8:[("basic",2),("fast",2),("brute",2),("tank",2),("swarm",3),("shielder",2),("spitter",2),("sniper_e",3),("hexer",3),("mortar",3),("bomber",2),("armored",3)],
}
BOSS_SCHEDULE={5:"boss_brute",8:"boss_mage",11:"boss_tank",14:"megaboss"}

def get_spawn_weights(wave):
    w=min(wave,max(SPAWN_TABLE.keys()))
    while w not in SPAWN_TABLE: w-=1
    table=list(SPAWN_TABLE[w])
    return [t for t,_ in table],[wt for _,wt in table]

class WaveManager:
    def __init__(self):
        self.wave=0; self.spawn_t=0; self.total=0; self.size=0
        self.between=False; self.between_cd=FPS*3; self.between_t=0; self.boss_spawned=False
    def start_wave(self):
        self.wave+=1; self.between=False; self.size=12+self.wave*7; self.total=0; self.spawn_t=0; self.boss_spawned=False
    def update(self,enemies,player):
        new=[]
        if self.between:
            self.between_t-=1
            if self.between_t<=0: self.start_wave()
            return new
        if not self.boss_spawned and self.wave in BOSS_SCHEDULE and len(enemies)==0 and self.total==0:
            a=random.uniform(0,math.tau); r=800
            new.append(Enemy(player.x+math.cos(a)*r,player.y+math.sin(a)*r,BOSS_SCHEDULE[self.wave]))
            self.boss_spawned=True; self.size=1; self.total=1; return new
        self.spawn_t-=1
        if self.total<self.size and self.spawn_t<=0:
            count=random.randint(1,min(4,self.size-self.total))
            for _ in range(count): new.append(self._spawn(player)); self.total+=1
            self.spawn_t=max(8,52-self.wave*3)
        if self.total>=self.size and len(enemies)==0:
            self.between=True; self.between_t=self.between_cd
        return new
    def _spawn(self,player):
        a=random.uniform(0,math.tau); r=random.uniform(680,950)
        x=player.x+math.cos(a)*r; y=player.y+math.sin(a)*r
        types,weights=get_spawn_weights(self.wave)
        return Enemy(x,y,random.choices(types,weights=weights)[0])

# ═══════ STRUCTURES ════════════════════════════════════════════════════════════
class Structure:
    def __init__(self,x,y,sdef):
        self.x,self.y=float(x),float(y); self.sdef=sdef
        self.radius=sdef["radius"]; self.color=sdef["color"]; self.shape=sdef["shape"]
        self.used=False; self.bob=random.uniform(0,math.tau); self.pulse=0.0; self.nearby=False
    def update(self,px,py):
        self.bob+=0.04; d=dist((self.x,self.y),(px,py))
        self.nearby=(d<self.radius+60)
        if self.nearby: self.pulse=(self.pulse+0.08)%math.tau
    def interact(self,player,save,acquired,particles):
        if self.used: return None
        self.used=True; rtype,rval=self.sdef["reward"]
        burst(particles,self.x,self.y,self.color,n=20,spd=7,sz=5,life=35)
        if rtype=="heal": player.hp=min(player.max_hp,player.hp+rval)
        elif rtype=="xp":
            amount=int(rval*getattr(player,"xp_mult",1.0)); player.gain_xp(amount)
        elif rtype=="random_upgrade":
            pool=[u for u in UPGRADE_LIST if _upg_ok(u,player,acquired)]
            if pool:
                u=random.choice(pool); u["apply"](player)
                acquired[u["id"]]=acquired.get(u["id"],0)+1
        elif rtype=="speed": player.speed+=rval
        elif rtype=="supercoins": save["supercoins"]=save.get("supercoins",0)+rval; write_save(save)
        elif rtype=="dmg": player.dmg+=rval
        elif rtype=="nova": player.has_nova=True; player.nova_cd=player.nova_interval
        # record in index
        sid=self.sdef["id"]
        if sid not in save.get("seen_structures",[]): save.setdefault("seen_structures",[]).append(sid)
        return self.sdef["interact_msg"]
    def draw(self,surf,ox,oy):
        if self.used: return
        sx,sy=int(self.x-ox),int(self.y-oy); col=self.color
        if self.nearby:
            glow_r=int(self.radius+10+math.sin(self.pulse)*6)
            r2,g2,b2=col
            pygame.draw.circle(surf,(r2//5,g2//5,b2//5),(sx,sy),glow_r)
        bob_y=int(math.sin(self.bob)*4); sy2=sy+bob_y
        if self.shape=="diamond":
            pts=[(sx,sy2-self.radius),(sx+self.radius,sy2),(sx,sy2+self.radius),(sx-self.radius,sy2)]
            pygame.draw.polygon(surf,col,pts); pygame.draw.polygon(surf,WHITE,pts,2)
        elif self.shape=="obelisk":
            hw=self.radius//2
            pygame.draw.polygon(surf,col,[(sx,sy2-self.radius),(sx+hw,sy2+self.radius//2),(sx-hw,sy2+self.radius//2)])
            pygame.draw.polygon(surf,WHITE,[(sx,sy2-self.radius),(sx+hw,sy2+self.radius//2),(sx-hw,sy2+self.radius//2)],2)
        elif self.shape=="box":
            r=self.radius-4
            pygame.draw.rect(surf,col,(sx-r,sy2-r,r*2,r*2),border_radius=4)
            pygame.draw.rect(surf,WHITE,(sx-r,sy2-r,r*2,r*2),2,border_radius=4)
        elif self.shape=="circle":
            pygame.draw.circle(surf,col,(sx,sy2),self.radius); pygame.draw.circle(surf,WHITE,(sx,sy2),self.radius,2)
            for i in range(6):
                a=math.tau*i/6+self.bob
                pygame.draw.circle(surf,WHITE,(int(sx+math.cos(a)*(self.radius-6)),int(sy2+math.sin(a)*(self.radius-6))),3)
        elif self.shape=="triangle":
            pts=[(sx,sy2-self.radius),(sx+self.radius,sy2+self.radius//2),(sx-self.radius,sy2+self.radius//2)]
            pygame.draw.polygon(surf,col,pts); pygame.draw.polygon(surf,WHITE,pts,2)
        elif self.shape=="star":
            pts=[]
            for i in range(10):
                a=math.tau*i/10-math.pi/2; r3=self.radius if i%2==0 else self.radius//2
                pts.append((int(sx+math.cos(a)*r3),int(sy2+math.sin(a)*r3)))
            pygame.draw.polygon(surf,col,pts); pygame.draw.polygon(surf,WHITE,pts,2)
        dtxt(surf,self.sdef["name"],font_xs,WHITE,sx,sy2+self.radius+12)
        if self.nearby: dtxt(surf,"[E] interact",font_xs,col,sx,sy2+self.radius+26)

class WorldEvent:
    def __init__(self,edef):
        self.edef=edef; self.timer=edef["duration"]; self.effect=edef["effect"]
        self.alive=True; self.progress_val=0; self.goal=edef.get("goal",0)
        self.announce_timer=FPS*4
    def update(self):
        self.timer-=1
        if self.timer<=0: self.alive=False
    @property
    def active(self): return self.alive
    def draw_banner(self,surf):
        if self.announce_timer>0: self.announce_timer-=1
        col=self.edef["color"]; by=H//2-80; bw=600; bx=W//2-bw//2
        alpha=int(200*min(1,self.announce_timer/20+0.5))
        s=pygame.Surface((bw,70),pygame.SRCALPHA); s.fill((0,0,0,alpha)); surf.blit(s,(bx,by))
        pygame.draw.rect(surf,col,(bx,by,bw,70),2,border_radius=8)
        dtxt(surf,"⚡ "+self.edef["name"],font_med,col,W//2,by+18)
        dtxt(surf,self.edef["desc"],font_xs,WHITE,W//2,by+44)
        if self.goal>0: dtxt(surf,f"Progress: {self.progress_val}/{self.goal}",font_xs,col,W//2,by+60)
    def draw_hud(self,surf):
        if not self.alive: return
        col=self.edef["color"]; bw=240; bh=18; bx=W-bw-18; by=H-130
        ratio=self.timer/self.edef["duration"]
        pygame.draw.rect(surf,(20,20,30),(bx-2,by-2,bw+4,bh+4),border_radius=4)
        pygame.draw.rect(surf,col,(bx,by,int(bw*ratio),bh),border_radius=3)
        pygame.draw.rect(surf,GRAY,(bx,by,bw,bh),1,border_radius=3)
        dtxt(surf,self.edef["name"]+" "+str(self.timer//FPS+1)+"s",font_xs,WHITE,bx+bw//2,by+9)

class StructureManager:
    SPAWN_INTERVAL=FPS*45; MAX_STRUCTURES=4
    def __init__(self):
        self.structures=[]; self.spawn_cd=FPS*20
        self.event=None; self.event_cd=FPS*60
        self.coin_particles=[]; self.freeze_timer=0
        self.xp_mult_bonus=1.0; self.xp_mult_timer=0
        self.dmg_mult_bonus=1.0; self.dmg_mult_timer=0
        self.coinfall_cd=0
    def update(self,player,save,acquired,particles):
        self.spawn_cd-=1
        if self.spawn_cd<=0 and len(self.structures)<self.MAX_STRUCTURES:
            self._try_spawn(player); self.spawn_cd=self.SPAWN_INTERVAL+random.randint(-FPS*10,FPS*10)
        for s in self.structures: s.update(player.x,player.y)
        self.event_cd-=1
        if self.event_cd<=0 and self.event is None:
            self._start_event(player,particles); self.event_cd=FPS*(80+random.randint(0,60))
        msgs=[]
        if self.event:
            self.event.update()
            ef=self.event.effect
            if ef=="xp_triple": self.xp_mult_bonus=3.0; self.xp_mult_timer=self.event.timer
            elif ef=="dmg_triple": self.dmg_mult_bonus=3.0; self.dmg_mult_timer=self.event.timer
            elif ef=="freeze": self.freeze_timer=self.event.timer
            elif ef=="coinfall":
                self.coinfall_cd-=1
                if self.coinfall_cd<=0:
                    self.coinfall_cd=8; rx=player.x+random.uniform(-400,400); ry=player.y+random.uniform(-400,400)
                    self.coin_particles.append(CoinParticle(rx,ry)); save["supercoins"]=save.get("supercoins",0)+1
            if not self.event.alive:
                if self.event.effect=="xp_triple": self.xp_mult_bonus=1.0
                if self.event.effect=="dmg_triple": self.dmg_mult_bonus=1.0
                if self.event.effect=="swarm_challenge" and self.event.progress_val>=self.event.goal:
                    player.gain_xp(400); msgs.append("SWARM COMPLETE! +400 XP")
                self.event=None
        for cp in self.coin_particles: cp.update()
        self.coin_particles=[cp for cp in self.coin_particles if cp.alive]
        if self.xp_mult_timer>0: self.xp_mult_timer-=1
        else: self.xp_mult_bonus=1.0
        if self.dmg_mult_timer>0: self.dmg_mult_timer-=1
        else: self.dmg_mult_bonus=1.0
        return msgs
    def is_frozen(self): return self.freeze_timer>0
    def is_bloodmoon(self): return self.event and self.event.effect=="bloodmoon" and self.event.alive
    def on_kill(self):
        if self.event and self.event.effect=="swarm_challenge": self.event.progress_val+=1
    def _try_spawn(self,player):
        sdef=random.choice(STRUCTURE_DEFS); a=random.uniform(0,math.tau); r=random.uniform(300,600)
        self.structures.append(Structure(player.x+math.cos(a)*r,player.y+math.sin(a)*r,sdef))
    def _start_event(self,player,particles):
        edef=random.choice(WORLD_EVENTS); self.event=WorldEvent(edef)
        burst(particles,player.x,player.y,edef["color"],n=20,spd=8,sz=5,life=40)
        # record seen
    def try_interact(self,player,save,acquired,particles):
        msgs=[]
        for s in self.structures:
            if s.used: continue
            if dist((player.x,player.y),(s.x,s.y))<player.radius+s.radius+20:
                result=s.interact(player,save,acquired,particles)
                if result: msgs.append(result if isinstance(result,str) else str(result))
        self.structures=[s for s in self.structures if not s.used]
        return msgs
    def draw(self,surf,ox,oy):
        for s in self.structures: s.draw(surf,ox,oy)
        for cp in self.coin_particles: cp.draw(surf,ox,oy)
        if self.event and self.event.active:
            self.event.draw_banner(surf); self.event.draw_hud(surf)

# ═══════ PROCESS RESULTS ═══════════════════════════════════════════════════════
def process_results(results,player,bullets,novas,lwaves,larcs,particles,enemies):
    for item in results:
        if not item: continue
        if isinstance(item,(Bullet,ChainBolt,PlasmaBall,SniperBolt)): bullets.append(item); continue
        if not isinstance(item,(tuple,list)) or len(item)<2:
            if hasattr(item,"dead"): bullets.append(item); continue
        if isinstance(item[0],str):
            tag,payload=item[0],item[1]
            if tag=="sword_dash":
                dx,dy,dmg,frames=payload; player.start_dash(dx,dy,dmg,frames); player.angle=math.atan2(dy,dx)
            elif tag=="raygun_mode": burst(particles,player.x,player.y,RAY_C,n=10,spd=4,sz=4,life=20)
            elif tag=="lightning_arc":
                (x1,y1),(x2,y2)=payload; larcs.append(LightningArc(x1,y1,x2,y2,life=14))
            elif tag=="lightning_wave": lwaves.append(payload)
            elif tag=="sniper_mark":
                for e in (payload if isinstance(payload,list) else []):
                    player.marked_enemies.add(id(e))
                player.mark_timer=FPS*5
            elif tag=="hexer_volley":
                _,ex,ey,dx2,dy2=item; base=math.atan2(dy2,dx2)
                for off in [-0.4,0,0.4]:
                    a2=base+off
                    bullets.append(Bullet(ex,ey,math.cos(a2),math.sin(a2),dmg=14,pierce=1,spd_m=.7,col=(80,200,255),size=8,lifetime=85,enemy=True))

def try_chain(bolt,enemies,particles):
    if bolt.jumps<=0: return None
    cands=[e for e in enemies if id(e) not in bolt.hit and e.alive]
    if not cands: return None
    t=min(cands,key=lambda e:dist((bolt.x,bolt.y),(e.x,e.y)))
    if dist((bolt.x,bolt.y),(t.x,t.y))>ChainBolt.CHAIN_R: return None
    burst(particles,bolt.x,bolt.y,CHAIN_C,n=6,spd=5,sz=4,life=18)
    nh=set(bolt.hit); nh.add(id(t))
    return ChainBolt(bolt.x,bolt.y,t.x-bolt.x,t.y-bolt.y,bolt.dmg,bolt.jumps-1,nh)

# ═══════ INDEX SCREEN ══════════════════════════════════════════════════════════
async def index_screen(save):
    tab=0  # 0=structures, 1=events
    while True:
        screen.fill(BG)
        for i in range(0,W,80): pygame.draw.line(screen,GRID_C,(i,0),(i,H))
        for j in range(0,H,80): pygame.draw.line(screen,GRID_C,(0,j),(W,j))
        pygame.draw.rect(screen,(15,15,30),(0,0,W,58))
        dtxt(screen,"FIELD INDEX",font_med,STRUCT_C,W//2,28)
        dtxt(screen,"TAB = switch  |  ESC = back",font_xs,GRAY,W//2,50)
        # Tab buttons
        for i,tn in enumerate(["STRUCTURES","EVENTS"]):
            bx=W//2-240+i*250; by=62; bw=220; bh=28
            col=STRUCT_C if i==0 else EVENT_C; active=(i==tab)
            pygame.draw.rect(screen,(25,35,35) if active else DGRAY,(bx,by,bw,bh),border_radius=6)
            pygame.draw.rect(screen,col,(bx,by,bw,bh),2,border_radius=6)
            dtxt(screen,tn,font_xs,col,bx+bw//2,by+14)

        seen_s=save.get("seen_structures",[])
        seen_e=save.get("seen_events",[])

        if tab==0:
            y0=100; bw=W-120; bh=68
            for i,sdef in enumerate(STRUCTURE_DEFS):
                sid=sdef["id"]; seen=(sid in seen_s)
                bx=60; by=y0+i*(bh+6)
                bg=(18,28,28) if seen else (20,20,28)
                col=sdef["color"] if seen else GRAY
                pygame.draw.rect(screen,bg,(bx,by,bw,bh),border_radius=8)
                pygame.draw.rect(screen,col,(bx,by,bw,bh),2 if seen else 1,border_radius=8)
                # shape icon mini
                ix=bx+40; iy=by+bh//2
                if seen:
                    if sdef["shape"]=="diamond":
                        pts=[(ix,iy-14),(ix+14,iy),(ix,iy+14),(ix-14,iy)]
                        pygame.draw.polygon(screen,col,pts)
                    elif sdef["shape"]=="star":
                        for k in range(10):
                            a=math.tau*k/10-math.pi/2; r3=14 if k%2==0 else 7
                            pts2=[] if k==0 else pts2
                            if k==0: pts2=[]
                            pts2.append((int(ix+math.cos(a)*r3),int(iy+math.sin(a)*r3)))
                        pygame.draw.polygon(screen,col,pts2)
                    else:
                        pygame.draw.circle(screen,col,(ix,iy),14,2)
                    dtxt(screen,sdef["name"],font_sm,WHITE,bx+160,by+20)
                    dtxt(screen,sdef["desc"],font_xs,GRAY,bx+160,by+44)
                    dtxt(screen,"DISCOVERED",font_xs,col,W-100,by+bh//2)
                else:
                    dtxt(screen,"??? UNDISCOVERED",font_sm,GRAY,bx+160,by+bh//2)
                    dtxt(screen,"Interact to reveal",font_xs,(60,60,80),W-130,by+bh//2)
        else:
            y0=100; bw=W-120; bh=68
            for i,edef in enumerate(WORLD_EVENTS):
                eid=edef["id"]; seen=(eid in seen_e)
                bx=60; by=y0+i*(bh+6)
                col=edef["color"] if seen else GRAY
                bg=(20,18,10) if seen else (20,20,28)
                pygame.draw.rect(screen,bg,(bx,by,bw,bh),border_radius=8)
                pygame.draw.rect(screen,col,(bx,by,bw,bh),2 if seen else 1,border_radius=8)
                if seen:
                    dtxt(screen,"⚡ "+edef["name"],font_sm,col,bx+140,by+20)
                    dtxt(screen,edef["desc"],font_xs,GRAY,bx+140,by+44)
                    secs=edef["duration"]//FPS
                    dtxt(screen,f"Duration: {secs}s",font_xs,col,W-120,by+bh//2)
                else:
                    dtxt(screen,"??? UNDISCOVERED EVENT",font_sm,GRAY,bx+140,by+bh//2)

        pygame.display.flip()
        await asyncio.sleep(0)
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_ESCAPE: return
                if ev.key==pygame.K_TAB: tab=1-tab

# ═══════ CARD LOG SCREEN ═══════════════════════════════════════════════════════
async def card_log_screen(acquired,player):
    """Show all upgrade cards chosen this run."""
    while True:
        screen.fill(BG)
        for i in range(0,W,80): pygame.draw.line(screen,GRID_C,(i,0),(i,H))
        for j in range(0,H,80): pygame.draw.line(screen,GRID_C,(0,j),(W,j))
        pygame.draw.rect(screen,(15,15,30),(0,0,W,58))
        dtxt(screen,"CARD LOG — UPGRADES THIS RUN",font_med,XP_C,W//2,28)
        dtxt(screen,"ESC to close",font_xs,GRAY,W//2,50)

        all_upgs=UPGRADE_LIST+make_super_upgrade_cards({"super_tier_unlocked":{},"super_tier_levels":{}})
        chosen=[u for u in all_upgs if acquired.get(u["id"],0)>0]

        # Draw in grid
        cw=200; ch=80; cols=5; gap=8
        total_w=cols*cw+(cols-1)*gap; sx2=(W-total_w)//2; y0=70
        for i,u in enumerate(chosen):
            col_i=i%cols; row_i=i//cols
            bx=sx2+col_i*(cw+gap); by=y0+row_i*(ch+gap)
            if by+ch>H-20: break  # off screen
            is_super=u.get("super",False)
            col=SUPER_C if is_super else u["color"]
            pygame.draw.rect(screen,DGRAY,(bx,by,cw,ch),border_radius=8)
            pygame.draw.rect(screen,col,(bx,by,cw,ch),2,border_radius=8)
            cnt=acquired.get(u["id"],0)
            dtxt(screen,u["name"],font_xs,WHITE,bx+cw//2,by+22)
            dtxt(screen,f"×{cnt}",font_sm,col,bx+cw//2,by+50)

        if not chosen:
            dtxt(screen,"No upgrades chosen yet.",font_sm,GRAY,W//2,H//2)

        pygame.display.flip()
        await asyncio.sleep(0)
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE,pygame.K_TAB): return

# ═══════ META UPGRADE SCREEN ═══════════════════════════════════════════════════
async def meta_upgrade_screen(save):
    tab=0; msg=""; msg_timer=0
    TAB_NAMES=["BASE UPGRADES","SUPER BRANCHES","SUPER TIER"]
    while True:
        screen.fill(BG)
        for i in range(0,W,80): pygame.draw.line(screen,GRID_C,(i,0),(i,H))
        for j in range(0,H,80): pygame.draw.line(screen,GRID_C,(0,j),(W,j))
        coins=save.get("supercoins",0)
        pygame.draw.rect(screen,(30,25,0),(0,0,W,58))
        dtxt(screen,"✦ META UPGRADES",font_med,COIN_C,W//2-200,28)
        dtxt(screen,f"SuperCoins: {coins}",font_med,COIN_C,W//2+180,28)
        dtxt(screen,"TAB=switch  1-8=buy  ESC=back  I=index",font_xs,GRAY,W//2,50)
        for i,tn in enumerate(TAB_NAMES):
            bx=180+i*200; by=62; bw=190; bh=28
            col=COIN_C if i==tab else GRAY
            pygame.draw.rect(screen,(40,35,0) if i==tab else DGRAY,(bx,by,bw,bh),border_radius=6)
            pygame.draw.rect(screen,col,(bx,by,bw,bh),2,border_radius=6)
            dtxt(screen,tn,font_xs,col,bx+bw//2,by+14)
        if tab==0: _draw_base_upgrades(screen,save,coins)
        elif tab==1: _draw_branch_unlocks(screen,save,coins)
        elif tab==2: _draw_super_tier(screen,save,coins)
        if msg_timer>0:
            msg_timer-=1
            dtxt(screen,msg,font_med,(100,255,120) if "✓" in msg else (255,100,100),W//2,H-48)
        pygame.display.flip()
        await asyncio.sleep(0)
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_ESCAPE: return
                if ev.key==pygame.K_TAB: tab=(tab+1)%3
                if ev.key==pygame.K_i: await index_screen(save)
                if ev.key in (pygame.K_1,pygame.K_2,pygame.K_3,pygame.K_4,pygame.K_5,pygame.K_6,pygame.K_7,pygame.K_8):
                    idx=ev.key-pygame.K_1; r,m=_try_buy(tab,idx,save)
                    msg=m; msg_timer=FPS*2; write_save(save)

def _draw_base_upgrades(surf,save,coins):
    mupg=save.get("meta_upgrades",{}); y0=100
    for i,m in enumerate(META_UPGRADES):
        uid,name,desc,base_cost,max_lvl,key,per=m; lvl=mupg.get(uid,0)
        bx=60; by=y0+i*62; bw=W-120; bh=54; full=(lvl>=max_lvl)
        pygame.draw.rect(surf,(20,30,20) if full else DGRAY,(bx,by,bw,bh),border_radius=8)
        pygame.draw.rect(surf,XP_C if full else COIN_C,(bx,by,bw,bh),2 if not full else 1,border_radius=8)
        cost=base_cost*(lvl+1) if not full else 0
        dtxt(surf,f"[{i+1}] {name}",font_sm,WHITE,bx+120,by+16); dtxt(surf,desc,font_xs,GRAY,bx+120,by+36)
        dtxt(surf,f"Lv {lvl}/{max_lvl}",font_sm,XP_C,W-260,by+16)
        if full: dtxt(surf,"MAXED",font_sm,XP_C,W-140,by+16)
        else:
            col=COIN_C if coins>=cost else (100,80,0)
            dtxt(surf,f"Cost: {cost} ✦",font_sm,col,W-140,by+27)
        hbar(surf,bx+4,by+bh-8,bw-8,5,lvl/max(1,max_lvl),XP_FG,XP_BG)

def _draw_branch_unlocks(surf,save,coins):
    unlocked=save.get("super_tier_unlocked",{}); y0=100; cw=(W-120)//len(SUPER_BRANCHES); gap=12
    for i,b in enumerate(SUPER_BRANCHES):
        bid,bname,bdesc,bcost,bcol=b; is_unl=unlocked.get(bid,False)
        bx=60+i*(cw+gap); by=y0; bh=200
        pygame.draw.rect(surf,(10,5,20) if not is_unl else (20,10,30),(bx,by,cw,bh),border_radius=12)
        pygame.draw.rect(surf,bcol,(bx,by,cw,bh),3 if is_unl else 1,border_radius=12)
        cx2=bx+cw//2
        pygame.draw.circle(surf,bcol,(cx2,by+50),22)
        if is_unl: pygame.draw.circle(surf,WHITE,(cx2,by+50),22,2)
        dtxt(surf,f"[{i+1}]",font_med,bcol,cx2,by+30); dtxt(surf,bname,font_sm,WHITE,cx2,by+88)
        dtxt(surf,bdesc,font_xs,GRAY,cx2,by+112)
        if is_unl: dtxt(surf,"UNLOCKED ✓",font_sm,XP_C,cx2,by+155)
        else:
            col=COIN_C if coins>=bcost else (100,80,0)
            dtxt(surf,f"Cost: {bcost} ✦",font_sm,col,cx2,by+155)
        dtxt(surf,f"{len([s for s in SUPER_UPGRADES if s[3]==bid])} upgrades",font_xs,(120,120,140),cx2,by+178)

def _draw_super_tier(surf,save,coins):
    unlocked=save.get("super_tier_unlocked",{}); levels=save.get("super_tier_levels",{})
    avail=[s for s in SUPER_UPGRADES if unlocked.get(s[3],False)]
    y0=100; bw=(W-140)//2; bh=80; gap=8
    for i,su in enumerate(avail):
        uid,name,desc,branch,cost,ms,eff=su; col=SUPER_C; lvl=levels.get(uid,0); full=(lvl>=ms)
        bx=70+(i%2)*(bw+gap); by=y0+(i//2)*(bh+gap)
        pygame.draw.rect(surf,(20,5,25) if not full else (10,20,10),(bx,by,bw,bh),border_radius=8)
        pygame.draw.rect(surf,col,(bx,by,bw,bh),2 if not full else 1,border_radius=8)
        surf.blit(font_sm.render(f"[{i+1}] {name}",True,SUPER_C),(bx+10,by+8))
        surf.blit(font_xs.render(desc,True,GRAY),(bx+10,by+32))
        if full: surf.blit(font_xs.render("MAXED",True,XP_C),(bx+10,by+54))
        else:
            total_cost=cost*(lvl+1); col2=COIN_C if coins>=total_cost else (100,80,0)
            surf.blit(font_xs.render(f"Cost: {total_cost}✦  Lv{lvl}/{ms}",True,col2),(bx+10,by+54))
        hbar(surf,bx+bw-80,by+8,70,8,lvl/max(1,ms),SUPER_C,(20,10,30))

def _try_buy(tab,idx,save):
    coins=save.get("supercoins",0)
    if tab==0:
        if idx>=len(META_UPGRADES): return False,"Invalid"
        m=META_UPGRADES[idx]; uid,name,_,base_cost,max_lvl,_,_=m
        lvl=save.get("meta_upgrades",{}).get(uid,0)
        if lvl>=max_lvl: return False,f"{name} MAXED"
        cost=base_cost*(lvl+1)
        if coins<cost: return False,f"Need {cost} ✦"
        save["supercoins"]-=cost; save.setdefault("meta_upgrades",{})[uid]=lvl+1
        return True,f"✓ {name} Lv{lvl+1}"
    elif tab==1:
        if idx>=len(SUPER_BRANCHES): return False,"Invalid"
        b=SUPER_BRANCHES[idx]; bid,bname,_,bcost,_=b
        if save.get("super_tier_unlocked",{}).get(bid,False): return False,f"{bname} already unlocked"
        if coins<bcost: return False,f"Need {bcost} ✦"
        save["supercoins"]-=bcost; save.setdefault("super_tier_unlocked",{})[bid]=True
        return True,f"✓ {bname} branch UNLOCKED"
    elif tab==2:
        unlocked=save.get("super_tier_unlocked",{})
        avail=[s for s in SUPER_UPGRADES if unlocked.get(s[3],False)]
        if idx>=len(avail): return False,"Invalid"
        su=avail[idx]; uid,name,_,_,cost,ms,_=su
        lvl=save.get("super_tier_levels",{}).get(uid,0)
        if lvl>=ms: return False,f"{name} MAXED"
        total_cost=cost*(lvl+1)
        if coins<total_cost: return False,f"Need {total_cost} ✦"
        save["supercoins"]-=total_cost; save.setdefault("super_tier_levels",{})[uid]=lvl+1
        return True,f"✓ {name} Lv{lvl+1}"
    return False,"?"

# ═══════ WEAPON SELECT ═════════════════════════════════════════════════════════
WEAPON_INFO={
    "pistol":("PISTOL","Balanced auto-fire. Range: 600\nQ: Burst — 5 rapid bullets.",BULLET_C),
    "sword":("SWORD","Melee arc. Range: 70-150\nQ: Dash  |  F: Parry bullets!",SWORD_C),
    "raygun":("RAYGUN","Lock-on beam. Range: 700\nQ: Switch targeting mode.",RAY_C),
    "lightning":("LIGHTNING","Hits enemies in range circle.\nRange: 280+  |  Q: Wave",LIGHTNING_C),
    "shotgun":("SHOTGUN","Spread pellets. Range: 350\nQ: 360° blast.",SHOTGUN_C),
    "plasma":("PLASMA","Exploding ball. Range: 550\nQ: Volley at 3 targets.",PLASMA_C),
    "sniper":("SNIPER","Targets farthest enemy.\nQ: Mark for +50% dmg.",SNIPER_C),
}

async def weapon_select_screen(save):
    weapons=list(WEAPON_INFO.keys()); selected=0
    while True:
        coins=save.get("supercoins",0)
        screen.fill(BG)
        for i in range(0,W,80): pygame.draw.line(screen,GRID_C,(i,0),(i,H))
        for j in range(0,H,80): pygame.draw.line(screen,GRID_C,(0,j),(W,j))
        dtxt(screen,"CHOOSE YOUR WEAPON",font_big,WHITE,W//2,60)
        dtxt(screen,f"← → browse   ENTER start   M=meta   I=index   ✦ {coins}",font_xs,GRAY,W//2,100)
        cw,ch=160,200; gap=18; total_w=len(weapons)*cw+(len(weapons)-1)*gap; start_x=W//2-total_w//2
        mx,my=pygame.mouse.get_pos()
        for i,wname in enumerate(weapons):
            bx=start_x+i*(cw+gap); by=H//2-ch//2-20
            info=WEAPON_INFO[wname]; col=info[2]; is_sel=(i==selected)
            hovering=(bx<=mx<=bx+cw and by<=my<=by+ch)
            if hovering: selected=i
            pygame.draw.rect(screen,(50,50,70) if is_sel else DGRAY,(bx,by,cw,ch),border_radius=14)
            pygame.draw.rect(screen,col if is_sel else (60,60,80),(bx,by,cw,ch),3 if is_sel else 1,border_radius=14)
            cx2=bx+cw//2
            pygame.draw.circle(screen,col,(cx2,by+45),22); pygame.draw.circle(screen,WHITE,(cx2,by+45),22,2)
            dtxt(screen,info[0],font_sm,WHITE if is_sel else GRAY,cx2,by+85)
            for dl,ln in enumerate(info[1].split("\n")): dtxt(screen,ln,font_xs,(200,200,200) if is_sel else (120,120,140),cx2,by+110+dl*18)
            if is_sel: dtxt(screen,"▼",font_med,col,cx2,by+ch+10)
        sel_info=WEAPON_INFO[weapons[selected]]
        dtxt(screen,sel_info[0],font_big,sel_info[2],W//2,H-70)
        dtxt(screen,"ENTER or click ▼ to start",font_sm,WHITE,W//2,H-35)
        pygame.display.flip()
        await asyncio.sleep(0)
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                if ev.key in (pygame.K_LEFT,pygame.K_a): selected=(selected-1)%len(weapons)
                if ev.key in (pygame.K_RIGHT,pygame.K_d): selected=(selected+1)%len(weapons)
                if ev.key==pygame.K_m: await meta_upgrade_screen(save)
                if ev.key==pygame.K_i: await index_screen(save)
                if ev.key in (pygame.K_RETURN,pygame.K_KP_ENTER,pygame.K_SPACE): return weapons[selected]
            if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                # click card to select, double-confirm already selected
                for i,wname in enumerate(weapons):
                    bx=start_x+i*(cw+gap); by=H//2-ch//2-20
                    if bx<=mx<=bx+cw and by<=my<=by+ch:
                        if i==selected: return weapons[selected]
                        selected=i; break

# ═══════ DEATH SCREEN ══════════════════════════════════════════════════════════
async def death_screen(save,wave,level,kills,boss_kills,score,weapon_name):
    cm_lvl=save.get("meta_upgrades",{}).get("m_coin_gain",0)
    mult=1.0+cm_lvl*0.15
    earned=int(calc_supercoins(wave,level,kills,boss_kills)*mult)
    save["supercoins"]=save.get("supercoins",0)+earned
    save["total_runs"]=save.get("total_runs",0)+1
    save["total_kills"]=save.get("total_kills",0)+kills
    if wave>save.get("best_wave",0): save["best_wave"]=wave
    write_save(save)
    t=0
    while True:
        screen.fill(BG)
        for i in range(0,W,80): pygame.draw.line(screen,GRID_C,(i,0),(i,H))
        for j in range(0,H,80): pygame.draw.line(screen,GRID_C,(0,j),(W,j))
        t+=1
        dtxt(screen,"YOU DIED",font_big,(220,50,50),W//2,H//2-180)
        dtxt(screen,f"Wave {wave}  •  Level {level}  •  {kills} kills  •  {boss_kills} bosses",font_med,WHITE,W//2,H//2-120)
        dtxt(screen,f"Score: {score}",font_sm,GRAY,W//2,H//2-85)
        bw=400; bx=W//2-bw//2; by=H//2-60
        pygame.draw.rect(screen,(40,30,0),(bx,by,bw,90),border_radius=14)
        pygame.draw.rect(screen,COIN_C,(bx,by,bw,90),2,border_radius=14)
        dtxt(screen,"SuperCoins Earned",font_sm,COIN_C,W//2,by+20)
        anim_coins=min(earned,int(earned*(t/60))) if t<60 else earned
        dtxt(screen,f"+ {anim_coins} ✦",font_big,COIN_C,W//2,by+58)
        dtxt(screen,f"Total: {save['supercoins']} ✦   Best wave: {save['best_wave']}",font_sm,COIN_C,W//2,H//2+60)
        dtxt(screen,"R=restart   M=meta upgrades   ESC=quit",font_sm,GRAY,W//2,H//2+138)
        pygame.display.flip()
        await asyncio.sleep(0)
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                if ev.key==pygame.K_r: return "restart"
                if ev.key==pygame.K_m: await meta_upgrade_screen(save); return "menu"

# ═══════ GAME LOOP ═════════════════════════════════════════════════════════════
async def game_loop(starting_weapon,save):
    player=Player(starting_weapon)
    apply_meta_to_player(player,save)
    for su in SUPER_UPGRADES:
        uid,_,_,_,_,_,eff=su
        if save.get("super_tier_levels",{}).get(uid,0)>0: player.apply_super(eff,save)

    bullets=[]; novas=[]; lwaves=[]; larcs=[]
    enemies=[]; orbs=[]; particles=[]; telegraphs=[]
    struct_mgr=StructureManager(); wm=WaveManager(); wm.start_wave()
    acquired={}; score=0; kills=0; boss_kills=0; shake=0
    ox=oy=0.0; state="play"; upgrades=[]; TILE=80
    ray_beam=None; ray_beam_t=0
    hud_msgs=[]; hud_msg_timer=0
    echo_bullets=[]
    upgrade_card_rects=[]   # for mouse click on upgrade cards

    while True:
        mx,my=pygame.mouse.get_pos()

        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                if state=="upgrade":
                    idx={pygame.K_1:0,pygame.K_2:1,pygame.K_3:2}.get(ev.key)
                    if idx is not None and idx<len(upgrades):
                        _apply_upgrade(upgrades[idx],player,acquired,save); state="play"
                    if ev.key==pygame.K_TAB: await card_log_screen(acquired,player)
                if state=="dead":
                    if ev.key in (pygame.K_r,pygame.K_m):
                        result=await death_screen(save,wm.wave,player.level,kills,boss_kills,score,starting_weapon)
                        if result=="restart": await game_loop(starting_weapon,save); return
                        else: sw=await weapon_select_screen(save); await game_loop(sw,save); return
                if state=="play":
                    if ev.key==pygame.K_q:
                        res=player.weapon.special(player.x,player.y,enemies,player.effective_dmg())
                        process_results(res,player,bullets,novas,lwaves,larcs,particles,enemies)
                    if ev.key==pygame.K_e:
                        msgs=struct_mgr.try_interact(player,save,acquired,particles)
                        for m in msgs: hud_msgs.append((m,FPS*2)); write_save(save)
                    if ev.key==pygame.K_f and player.weapon.name=="sword":
                        player.weapon.try_parry(player.x,player.y)
                    if ev.key==pygame.K_TAB:
                        await card_log_screen(acquired,player)
                    if ev.key==pygame.K_i:
                        await index_screen(save)
            if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                if state=="upgrade":
                    for i,(bx3,by3,bw3,bh3) in enumerate(upgrade_card_rects):
                        if bx3<=mx<=bx3+bw3 and by3<=my<=by3+bh3 and i<len(upgrades):
                            _apply_upgrade(upgrades[i],player,acquired,save); state="play"; break

        if state=="play":
            keys=pygame.key.get_pressed()
            player.move(keys); player.update(enemies,particles)
            ox=player.x-W//2; oy=player.y-H//2; shake=max(0,shake-1)
            enemies.extend(wm.update(enemies,player))
            smsg=struct_mgr.update(player,save,acquired,particles)
            for m in smsg: hud_msgs.append((m,FPS*3))
            for s in struct_mgr.structures:
                if not s.used and dist((player.x,player.y),(s.x,s.y))<player.radius+s.radius+12:
                    msgs2=struct_mgr.try_interact(player,save,acquired,particles)
                    for m in msgs2: hud_msgs.append((m,FPS*2)); write_save(save)

            pdmg=int(player.effective_dmg()*struct_mgr.dmg_mult_bonus)

            # Auto-shoot
            res=player.weapon.shoot(player.x,player.y,enemies,pdmg)
            if player.echo_chance>0 and res and random.random()<player.echo_chance:
                echo_bullets.extend(res)
            process_results(res,player,bullets,novas,lwaves,larcs,particles,enemies)
            bullets.extend(echo_bullets); echo_bullets.clear()

            if res:
                if player.weapon.name=="pistol": burst(particles,player.x,player.y,BULLET_C,n=4,spd=5,sz=3,life=12)
                if player.weapon.name=="lightning": burst(particles,player.x,player.y,LIGHTNING_C,n=4,spd=5,sz=3,life=12)

            # Raygun beam
            if player.weapon.name=="raygun":
                w2=player.weapon
                if w2.locked_target and w2.locked_target in enemies and w2.locked_target.alive:
                    t=w2.locked_target; ray_beam=(t.x,t.y); ray_beam_t=6
                    player.angle=math.atan2(t.y-player.y,t.x-player.x)
            ray_beam_t=max(0,ray_beam_t-1)

            # Nova
            if player.has_nova and player.nova_cd<=0:
                player.nova_cd=player.nova_interval
                novas.append(NovaBurst(player.x,player.y,pdmg*2))
                burst(particles,player.x,player.y,NOVA_C,n=20,spd=7,sz=5,life=25)

            is_frozen=struct_mgr.is_frozen(); is_bloodmoon=struct_mgr.is_bloodmoon()

            new_enemy_bullets=[]
            for e in enemies:
                e.move_toward(player.x,player.y,is_frozen)
                if not is_frozen:
                    proj=e.try_shoot(player.x,player.y,telegraphs)
                    if proj:
                        if isinstance(proj,tuple) and len(proj)>=1 and proj[0]=="hexer_volley":
                            process_results([proj],player,bullets,novas,lwaves,larcs,particles,enemies)
                        elif proj is not None: new_enemy_bullets.append(proj)
                    boss_projs=e.try_boss_action(player.x,player.y,bullets,particles,telegraphs)
                    new_enemy_bullets.extend(boss_projs)
                contact_dmg=e.contact_dmg*(2 if is_bloodmoon else 1)
                if dist((player.x,player.y),(e.x,e.y))<player.radius+e.radius:
                    if e.etype=="bomber" and not e.exploded:
                        e.exploded=True; e.hp=0; e.alive=False
                        burst(particles,e.x,e.y,(255,80,0),n=20,spd=8,sz=6,life=35)
                        for nb in enemies:
                            if nb is not e and dist((e.x,e.y),(nb.x,nb.y))<80: nb.take_damage(40)
                    was_hit=player.take_damage(contact_dmg)
                    if was_hit:
                        td=player.thorns_dmg(contact_dmg)
                        if td>0: e.take_damage(td)
                        if not player.dashing: shake=14; burst(particles,player.x,player.y,(255,80,80),n=8,spd=5,sz=4,life=22)
            bullets.extend(new_enemy_bullets)

            for tw in telegraphs: tw.update()
            telegraphs=[tw for tw in telegraphs if tw.alive]

            new_bolts=[]
            for b in list(bullets):
                b.update()
                if isinstance(b,PlasmaBall) and not b.exploded:
                    for e in (enemies if not b.enemy else []):
                        if dist((b.x,b.y),(e.x,e.y))<e.radius+b.sz: b.explode(enemies,particles); break
                    if b.enemy and dist((b.x,b.y),(player.x,player.y))<player.radius+b.sz:
                        b.explode([],particles); player.take_damage(b.dmg)
                elif isinstance(b,ChainBolt) and not b.enemy:
                    for e in enemies:
                        if id(e) in b.hit or not e.alive: continue
                        if dist((b.x,b.y),(e.x,e.y))<e.radius+6:
                            b.hit.add(id(e)); e.take_damage(b.dmg)
                            burst(particles,e.x,e.y,CHAIN_C,n=7,spd=4,sz=3,life=20)
                            nb2=try_chain(b,enemies,particles)
                            if nb2: new_bolts.append(nb2)
                            b.life=0; break
                elif b.enemy:
                    if dist((b.x,b.y),(player.x,player.y))<player.radius+b.sz:
                        # Check sword parry
                        parried=False
                        if player.weapon.name=="sword":
                            p=player.weapon.check_parry_bullet(b.x,b.y,player.x,player.y,particles)
                            if p:
                                parried=True
                                # counter: deal dmg back to nearest enemy
                                counter_dmg=int(b.dmg*2)
                                near=[e for e in enemies]
                                if near:
                                    t3=min(near,key=lambda e:dist((player.x,player.y),(e.x,e.y)))
                                    t3.take_damage(counter_dmg)
                                    burst(particles,t3.x,t3.y,PARRY_C,n=12,spd=6,sz=4,life=25)
                                b.life=0
                        if not parried:
                            player.take_damage(b.dmg)
                            burst(particles,player.x,player.y,(255,80,80),n=6,spd=4,sz=3,life=18)
                            b.pierce-=1; shake=8
                else:
                    for e in enemies:
                        if id(e) in b.hit or not e.alive: continue
                        if dist((b.x,b.y),(e.x,e.y))<e.radius+b.sz:
                            b.hit.add(id(e)); b.pierce-=1
                            dmg=b.dmg
                            if id(e) in player.marked_enemies and player.mark_timer>0: dmg=int(dmg*1.5)
                            e.take_damage(dmg,player.curse_bonus)
                            burst(particles,e.x,e.y,(255,180,80),n=7,spd=4,sz=3,life=20)
            bullets.extend(new_bolts)
            bullets=[b for b in bullets if not b.dead]

            for n in novas: n.update(enemies,particles)
            novas=[n for n in novas if n.alive]
            for lw in lwaves: lw.update(enemies,particles)
            lwaves=[lw for lw in lwaves if lw.alive]
            for la in larcs: la.life-=1
            larcs=[la for la in larcs if la.life>0]
            for saw in player.saws: saw.check_hits(enemies,player.x,player.y,particles)

            # Record events in index
            if struct_mgr.event and struct_mgr.event.alive:
                eid=struct_mgr.event.edef["id"]
                if eid not in save.get("seen_events",[]): save.setdefault("seen_events",[]).append(eid)

            live=[]
            for e in enemies:
                if not e.alive:
                    xp_val=int(e.xp*struct_mgr.xp_mult_bonus*(2 if is_bloodmoon else 1))
                    orbs.append(XPOrb(e.x,e.y,xp_val)); score+=xp_val; kills+=1
                    if e.is_boss: boss_kills+=1
                    burst(particles,e.x,e.y,e.color,n=14,spd=5,sz=5,life=30)
                    player.on_kill(e,particles,live)
                    struct_mgr.on_kill()
                else: live.append(e)
            enemies=live

            for orb in list(orbs):
                orb.update(player.x,player.y,player.magnet_r)
                if dist((player.x,player.y),(orb.x,orb.y))<player.radius+orb.r+8:
                    lv=player.gain_xp(orb.val); orb.alive=False
                    if lv: state="upgrade"; upgrades=pick_upgrades(player,acquired,save,3)
            orbs=[o for o in orbs if o.alive]
            for p in particles: p.update()
            particles=[p for p in particles if p.life>0]
            if hud_msg_timer>0: hud_msg_timer-=1
            if hud_msgs and hud_msg_timer<=0: hud_msg_timer=hud_msgs[0][1]; hud_msgs.pop(0)
            if player.hp<=0: state="dead"

        # ── DRAW ─────────────────────────────────────────────────────────────
        screen.fill(BG)
        sxo=random.randint(-shake,shake) if shake else 0
        syo=random.randint(-shake,shake) if shake else 0
        rx,ry=ox-sxo,oy-syo

        if state=="play" and struct_mgr.is_bloodmoon():
            bm=pygame.Surface((W,H),pygame.SRCALPHA); bm.fill((80,0,0,30)); screen.blit(bm,(0,0))

        for gx in range(int(rx//TILE)*TILE,int(rx+W)+TILE,TILE): pygame.draw.line(screen,GRID_C,(int(gx-rx),0),(int(gx-rx),H))
        for gy in range(int(ry//TILE)*TILE,int(ry+H)+TILE,TILE): pygame.draw.line(screen,GRID_C,(0,int(gy-ry)),(W,int(gy-ry)))

        struct_mgr.draw(screen,rx,ry)

        for saw in player.saws:
            pygame.draw.circle(screen,(25,45,55),(int(player.x-rx),int(player.y-ry)),saw.orbit_r,1)
            saw.draw(screen,player.x,player.y,rx,ry)

        for tw in telegraphs: tw.draw(screen,rx,ry)
        for o in orbs: o.draw(screen,rx,ry)
        for n in novas: n.draw(screen,rx,ry)
        for lw in lwaves: lw.draw(screen,rx,ry)
        for la in larcs: la.draw(screen,rx,ry)

        if ray_beam_t>0 and ray_beam:
            t2=ray_beam_t/6; bx2,by2=int(ray_beam[0]-rx),int(ray_beam[1]-ry)
            pygame.draw.line(screen,lerp_col((20,80,40),RAY_C,t2),(W//2,H//2),(bx2,by2),max(1,int(4*t2)))
            pygame.draw.circle(screen,RAY_C,(bx2,by2),8)

        for b in bullets: b.draw(screen,rx,ry)
        for p in particles: p.draw(screen)
        for e in enemies: e.draw(screen,rx,ry)
        player.draw(screen)

        # ── HUD ──────────────────────────────────────────────────────────────
        hbar(screen,18,H-64,300,22,player.hp/player.max_hp,HP_FG)
        dtxt(screen,f"HP  {max(0,player.hp)}/{player.max_hp}",font_sm,WHITE,169,H-53)
        hbar(screen,18,H-36,300,18,player.xp/player.xp_next,XP_FG,XP_BG)
        dtxt(screen,f"LV {player.level}  •  {player.xp}/{player.xp_next} XP",font_sm,XP_C,169,H-27)

        if wm.between: wi=f"WAVE {wm.wave} CLEAR!  next in {wm.between_t//FPS+1}s"
        else: wi=f"WAVE {wm.wave}  —  {len(enemies)} enemies"
        dtxt(screen,wi,font_med,WHITE,W//2,22)
        dtxt(screen,f"KILLS {kills}   SCORE {score}   BOSSES {boss_kills}",font_xs,GRAY,W//2,46)
        dtxt(screen,f"✦ {save.get('supercoins',0)}",font_med,COIN_C,W-80,28)

        wcol=WEAPON_COLORS.get(player.weapon.name,WHITE)
        panel=[(f"WEAPON {player.weapon.name.upper()}",wcol),(f"DMG    {pdmg if state=='play' else player.dmg}",BULLET_C),
               (player.weapon.special_label(),wcol if player.weapon.special_cd<=0 else GRAY)]
        if player.weapon.special_cd>0: panel[-1]=(f"  CD {player.weapon.special_cd//FPS+1}s",GRAY)
        if player.weapon.name=="sword":
            sw=player.weapon
            if sw.parry_cd>0: panel.append((f"PARRY CD {sw.parry_cd//FPS+1}s",GRAY))
            elif sw.parrying: panel.append(("PARRYING!",PARRY_C))
            else: panel.append(("F=PARRY RDY",PARRY_C))
        if player.num_saws>0: panel.append((f"SAWS   {player.num_saws}",SAW_C))
        if player.has_nova:
            label="RDY" if player.nova_cd<=0 else f"{player.nova_cd//FPS+1}s"
            panel.append((f"NOVA   {label}",NOVA_C))
        if player.mark_timer>0: panel.append(("MARKED!",SNIPER_C))
        if player.weapon.name=="raygun" and hasattr(player.weapon,"lock_dmg"):
            panel.append((f"LOCK x{player.weapon.lock_dmg:.1f}",RAY_C))
        if player.evasion_chance>0: panel.append((f"EVADE {int(player.evasion_chance*100)}%",SUPER_C))
        if player.dmg_bonus_timer>0: panel.append(("FRENZY!",SUPER_C))
        if state=="play" and struct_mgr.dmg_mult_bonus>1: panel.append((f"DMG x{struct_mgr.dmg_mult_bonus:.0f}!",EVENT_C))
        if state=="play" and struct_mgr.xp_mult_bonus>1: panel.append((f"XP  x{struct_mgr.xp_mult_bonus:.0f}!",EVENT_C))

        ph=12+len(panel)*18
        pygame.draw.rect(screen,DGRAY,(12,12,182,ph),border_radius=6)
        for i,(txt,col) in enumerate(panel): dtxt(screen,txt,font_xs,col,100,22+i*18)

        # Tab hint
        dtxt(screen,"TAB=card log  I=index",font_xs,(60,60,90),W-110,H-18)

        # HUD floating message
        if hud_msg_timer>0 and hud_msgs:
            s=font_med.render(hud_msgs[0][0],True,STRUCT_C)
            screen.blit(s,s.get_rect(center=(W//2,H//2-150)))

        # Structure nearby hint
        for s2 in struct_mgr.structures:
            if not s2.used and dist((player.x,player.y),(s2.x,s2.y))<s2.radius+80:
                dtxt(screen,f"[E] {s2.sdef['name']}: {s2.sdef['desc'].split('.')[0]}",font_sm,STRUCT_C,W//2,H-100)
                break

        # ── UPGRADE SCREEN ────────────────────────────────────────────────────
        upgrade_card_rects=[]
        if state=="upgrade":
            ov=pygame.Surface((W,H),pygame.SRCALPHA); ov.fill((0,0,0,195)); screen.blit(ov,(0,0))
            dtxt(screen,f"LEVEL {player.level}!",font_big,XP_C,W//2,H//2-220)
            dtxt(screen,"Choose upgrade   1/2/3  or  CLICK   |   TAB=card log",font_sm,GRAY,W//2,H//2-175)
            cw2,ch2=225,200; gap2=22
            tw2=len(upgrades)*cw2+(len(upgrades)-1)*gap2; sx2=W//2-tw2//2
            for i,u in enumerate(upgrades):
                bx3=sx2+i*(cw2+gap2); by3=H//2-120
                upgrade_card_rects.append((bx3,by3,cw2,ch2))
                is_super=u.get("super",False)
                cat_col=SUPER_C if is_super else (BULLET_C if u["cat"]=="gun" else SAW_C)
                hovering=(bx3<=mx<=bx3+cw2 and by3<=my<=by3+ch2)
                bg=DGRAY if not hovering else (60,60,80)
                pygame.draw.rect(screen,bg,(bx3,by3,cw2,ch2),border_radius=12)
                border_col=SUPER_C if is_super else u["color"]
                bwidth=4 if hovering else (3 if is_super else 2)
                pygame.draw.rect(screen,border_col,(bx3,by3,cw2,ch2),bwidth,border_radius=12)
                badge="SUPER" if is_super else ("GUN" if u["cat"]=="gun" else "CHAR")
                pygame.draw.rect(screen,cat_col,(bx3+4,by3+4,48 if is_super else 38,16),border_radius=4)
                dtxt(screen,badge,font_xs,(10,10,18),bx3+(26 if is_super else 23),by3+12)
                cx3=bx3+cw2//2
                dtxt(screen,str(i+1),font_big,u["color"],cx3,by3+48)
                dtxt(screen,u["name"],font_sm,WHITE,cx3,by3+92)
                for dl,ln in enumerate(u["desc"].split("\n")):
                    dtxt(screen,ln,font_xs,GRAY,cx3,by3+114+dl*16)
                st=acquired.get(u["id"],0); ms=u["max_stack"]
                dtxt(screen,f"[{st}/{ms}]" if ms else f"[{st}+]",font_xs,(80,80,110),cx3,by3+178)
                if hovering: dtxt(screen,"CLICK",font_xs,WHITE,cx3,by3+ch2-8)

        # ── DEAD SCREEN ───────────────────────────────────────────────────────
        if state=="dead":
            ov=pygame.Surface((W,H),pygame.SRCALPHA); ov.fill((0,0,0,215)); screen.blit(ov,(0,0))
            dtxt(screen,"YOU DIED",font_big,(220,50,50),W//2,H//2-120)
            dtxt(screen,f"Wave {wm.wave}  •  Kills {kills}  •  Score {score}",font_med,WHITE,W//2,H//2-50)
            dtxt(screen,f"Bosses killed: {boss_kills}",font_sm,BOSS_C,W//2,H//2-10)
            dtxt(screen,"R / M = results & coins",font_sm,GRAY,W//2,H//2+75)

        pygame.display.flip()
        await asyncio.sleep(0)

def _apply_upgrade(upg,player,acquired,save):
    upg["apply"](player)
    acquired[upg["id"]]=acquired.get(upg["id"],0)+1
    if upg.get("super"):
        save.setdefault("super_tier_levels",{})[upg["id"]]=save.get("super_tier_levels",{}).get(upg["id"],0)+1

# ═══════ TITLE ═════════════════════════════════════════════════════════════════
async def title_screen(save):
    while True:
        screen.fill(BG)
        for i in range(0,W,80): pygame.draw.line(screen,GRID_C,(i,0),(i,H))
        for j in range(0,H,80): pygame.draw.line(screen,GRID_C,(0,j),(W,j))
        dtxt(screen,"HORDE SURVIVOR",font_huge,PLAYER_C,W//2,H//2-150)
        dtxt(screen,"Auto-aim  ·  Collect XP  ·  Level up  ·  Survive",font_sm,GRAY,W//2,H//2-88)
        coins=save.get("supercoins",0)
        if coins>0: dtxt(screen,f"✦ {coins} SuperCoins",font_med,COIN_C,W//2,H//2-55)
        pygame.draw.rect(screen,DGRAY,(W//2-155,H//2-28,310,58),border_radius=10)
        pygame.draw.rect(screen,PLAYER_C,(W//2-155,H//2-28,310,58),2,border_radius=10)
        dtxt(screen,"PRESS  ENTER  TO  PLAY",font_med,WHITE,W//2,H//2+1)
        pygame.draw.rect(screen,DGRAY,(W//2-200,H//2+42,400,38),border_radius=8)
        pygame.draw.rect(screen,COIN_C,(W//2-200,H//2+42,400,38),2,border_radius=8)
        dtxt(screen,"M=META UPGRADES    I=INDEX",font_sm,COIN_C,W//2,H//2+61)
        tips=["WASD=move  Q=special  E=interact  F=parry(sword)  TAB=card log  I=index",
              "Kill enemies → XP → level up → choose upgrades (click or press 1/2/3)",
              "Die → earn SuperCoins based on wave/level/kills/bosses",
              "Find glowing structures  |  World events trigger automatically",
              "Lightning has a visible range circle  |  Sword can parry bullets with F",
              "Bosses: waves 5, 8, 11, 14…"]
        for k,tip in enumerate(tips): dtxt(screen,tip,font_xs,(100,100,150),W//2,H//2+95+k*18)
        pygame.display.flip()
        await asyncio.sleep(0)
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                if ev.key==pygame.K_m: await meta_upgrade_screen(save)
                if ev.key==pygame.K_i: await index_screen(save)
                if ev.key in (pygame.K_RETURN,pygame.K_KP_ENTER,pygame.K_SPACE): return


import asyncio

async def main():
    global screen, clock, font_huge, font_big, font_med, font_sm, font_xs
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("HORDE SURVIVOR v3")
    clock = pygame.time.Clock()
    font_huge = pygame.font.SysFont("consolas", 56, bold=True)
    font_big  = pygame.font.SysFont("consolas", 42, bold=True)
    font_med  = pygame.font.SysFont("consolas", 24, bold=True)
    font_sm   = pygame.font.SysFont("consolas", 16)
    font_xs   = pygame.font.SysFont("consolas", 13)
    save = load_save()
    await title_screen(save)
    while True:
        sw = await weapon_select_screen(save)
        await game_loop(sw, save)
        await asyncio.sleep(0)

asyncio.run(main())