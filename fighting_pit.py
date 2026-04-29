import pygame
import sys
import json
import os
import random
import math
import socket
import threading

# INITIALISATION
pygame.init()
pygame.mixer.init(frequency=44100, size=8, channels=1)

# CONFIGURATION
LARGEUR, HAUTEUR = 900, 600
fenetre = pygame.display.set_mode((LARGEUR, HAUTEUR))
pygame.display.set_caption("Fighting Pit - Online")

clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 40)
font_big = pygame.font.SysFont(None, 90)
font_small = pygame.font.SysFont(None, 28)
font_timer = pygame.font.SysFont(None, 120)

# COULEURS
BLANC = (255, 255, 255); ROUGE = (220, 60, 60); VERT = (60, 200, 80)
BLEU = (70, 130, 255); GRIS = (40, 40, 60); JAUNE = (255, 215, 0)
FOND = (15, 15, 25); OR = (255, 190, 0); NOIR = (10, 10, 10); MAUVE = (160, 32, 240); ORANGE = (180, 20, 0); BRUN = (88, 41, 0)

# ====DONNÉES DES SKINS (Dans le SHOP)===
SKINS_DATA = {
    "Basique": [BLEU, BLANC, 0],
    "Neon": [(57, 255, 20), BLANC, 200],
    "Lave": [(180, 20, 0), (255, 120, 0), 500],
    "Ombre": [NOIR, (160, 32, 240), 1000],
    "Diamant": [(135, 206, 250), (220, 220, 220), 2500],
    "Or": [(255, 215, 0), BLANC, 5000],
    "Soleil": [JAUNE, ORANGE, 7500],
    "Horreur": [NOIR, ORANGE, 10000],
    "Caca": [BRUN, NOIR, 12500]
}

# SONS
def make_tone(freq=440, duration=0.05, volume=60):
    sr = 44100
    length = int(sr * duration)
    buf = bytearray()
    for i in range(length):
        t = i / sr
        wave = math.sin(2 * math.pi * freq * t)
        val = int(128 + wave * volume)
        buf.append(max(0, min(255, val)))
    return pygame.mixer.Sound(buffer=bytes(buf))

snd_click = make_tone(600, 0.05, 50)
snd_error = make_tone(180, 0.12, 70)
snd_success = make_tone(900, 0.08, 60)
snd_tick = make_tone(1200, 0.1, 40)

# GESTION DES UTILISATEURS
USERS_DIR = "users"
os.makedirs(USERS_DIR, exist_ok=True)

def user_path(name):
    return os.path.join(USERS_DIR, name)

def load_user(name):
    try:
        path = os.path.join(user_path(name), "data.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                if "owned_skins" not in data: data["owned_skins"] = ["Basique"]
                if "equipped_skin" not in data: data["equipped_skin"] = "Basique"
                if "losses" not in data: data["losses"] = 0  # === AJOUT : champ défaites ===
                return data
    except Exception: return None
    return None

def save_user(name, data):
    path = user_path(name)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "data.json"), "w") as f:
        json.dump(data, f, indent=4)

def login_user(name, pwd):
    data = load_user(name)
    return data and data.get("pwd") == pwd

def create_user(name, pwd):
    if load_user(name): return False
    # === AJOUT : champ losses dès la création ===
    save_user(name, {"pwd": pwd, "wins": 0, "losses": 0, "money": 0, "owned_skins": ["Basique"], "equipped_skin": "Basique"})
    return True

# === AJOUT : Charger tous les joueurs pour le classement ===
def load_all_users():
    """Retourne une liste de (nom, wins, losses, money) triée par victoires décroissantes."""
    joueurs = []
    if not os.path.exists(USERS_DIR):
        return joueurs
    for nom in os.listdir(USERS_DIR):
        data = load_user(nom)
        if data and "wins" in data:
            joueurs.append({
                "nom": nom,
                "wins": data.get("wins", 0),
                "losses": data.get("losses", 0),
                "money": data.get("money", 0),
            })
    # Trier par victoires décroissantes, puis par nom alphabétique en cas d'égalité
    joueurs.sort(key=lambda j: (-j["wins"], j["nom"].lower()))
    return joueurs

#===RANG===

def get_rank_info(wins):
    if wins < 1: return "DÉBUTANT", 1, GRIS
    if wins < 10: return "RECRUE", 2, BLANC
    if wins < 25: return "COMBATTANT", 3, VERT
    if wins < 50: return "GUERRIER", 4, BLEU
    if wins < 100: return "ELITE", 5, ROUGE
    if wins < 150: return "LEGENDE", 6, OR
    if wins < 200: return "PRO", 7, ORANGE
    if wins < 300: return "FUTUR", 8, (255, 205, 153)
    return "SECRET", 9, MAUVE

# En ligne
class Network:
    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server = "localhost"
        self.port = 5555
        self.addr = (self.server, self.port)
        self.p_id = None

    def connect(self):
        try:
            self.client.connect(self.addr)
            self.p_id = int(self.client.recv(2048).decode())
            return True
        except: return False

    def send(self, data):
        try:
            self.client.send(str.encode(json.dumps(data)))
            return json.loads(self.client.recv(2048).decode())
        except socket.error as e:
            print(e)
            return None

def server_thread():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try: s.bind(("0.0.0.0", 5555))
    except socket.error: return
    s.listen(2)
    print("Serveur de matchmaking lancé...")
    
    connections = []
    game_state = {"0": None, "1": None}

    def threaded_client(conn, p_id):
        conn.send(str.encode(str(p_id)))
        while True:
            try:
                data = conn.recv(2048).decode()
                if not data: break
                game_state[str(p_id)] = json.loads(data)
                conn.sendall(str.encode(json.dumps(game_state)))
            except: break
        print(f"Joueur {p_id} déconnecté")
        conn.close()

    while len(connections) < 2:
        conn, addr = s.accept()
        p_id = len(connections)
        connections.append(conn)
        threading.Thread(target=threaded_client, args=(conn, p_id), daemon=True).start()

# CLASSES
class Joueur:
    def __init__(self, x, y, skin_name, controles, nom):
        self.rect = pygame.Rect(x, y, 50, 50)
        self.update_skin(skin_name)
        self.nom = nom
        self.vitesse = 5
        self.vies_max = 5
        self.vies = 5
        self.controles = controles
        self.classe = "attaque"
        self.last_attack = 0

    def update_skin(self, skin_name):
        s_info = SKINS_DATA.get(skin_name, SKINS_DATA["Basique"])
        self.couleur = s_info[0]
        self.bordure = s_info[1]

    def move(self):
        keys = pygame.key.get_pressed()
        if self.controles.get("gauche") and keys[self.controles["gauche"]]: self.rect.x -= self.vitesse
        if self.controles.get("droite") and keys[self.controles["droite"]]: self.rect.x += self.vitesse
        if self.controles.get("haut") and keys[self.controles["haut"]]: self.rect.y -= self.vitesse
        if self.controles.get("bas") and keys[self.controles["bas"]]: self.rect.y += self.vitesse
        self.rect.clamp_ip(pygame.Rect(0, 0, LARGEUR, HAUTEUR))

    def draw(self, surface):
        pygame.draw.rect(surface, self.couleur, self.rect, border_radius=10)
        pygame.draw.rect(surface, self.bordure, self.rect, 3, border_radius=10)
        bar_w = 50
        pygame.draw.rect(surface, ROUGE, (self.rect.x, self.rect.y - 15, bar_w, 6))
        pygame.draw.rect(surface, VERT, (self.rect.x, self.rect.y - 15, (max(0, self.vies)/self.vies_max)*bar_w, 6))

class Bouton:
    def __init__(self, x, y, w, h, text, color=GRIS, is_shop=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.base_color = color
        self.is_shop = is_shop

    def draw(self, surface):
        mx, my = pygame.mouse.get_pos()
        color = (90, 140, 255) if self.rect.collidepoint((mx, my)) else self.base_color
        pygame.draw.rect(surface, color, self.rect, border_radius=15)
        pygame.draw.rect(surface, BLANC, self.rect, 2, border_radius=15)
        
        if self.is_shop:
            r = self.rect
            cx, cy = r.centerx, r.centery
            panier_col = (255, 230, 150)
            pygame.draw.lines(surface, panier_col, False, [(cx-15, cy-12), (cx-15, cy-20), (cx+15, cy-20), (cx+15, cy-12)], 3)
            points_panier = [(cx-18, cy-12), (cx+18, cy-12), (cx+14, cy+12), (cx-14, cy+12)]
            pygame.draw.polygon(surface, panier_col, points_panier)
            pygame.draw.polygon(surface, BLANC, points_panier, 2)
        else:
            txt = font.render(self.text, True, BLANC)
            surface.blit(txt, txt.get_rect(center=self.rect.center))

    def click(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            snd_click.play(); return True
        return False

# ÉTATS
AUTH, LOGIN, REGISTER, MENU, STATS, SETTINGS, CONFIRM, JEU_MODE, JEU_COMBAT, FIN, SHOP, SEARCHING, CLASSEMENT = \
    "auth", "login", "register", "menu", "stats", "settings", "confirm", "jeu_mode", "jeu_combat", "fin", "shop", "searching", "classement"
# === AJOUT : état CLASSEMENT ===

etat = AUTH
current_user = None
input_text = ""; input_mode = "name"; temp_name = ""; error_text = ""; pwd_buffer = ""
game_mode = 1; p1, p2 = None, None; game_timer = 0; last_timer_sec = 0; gagnant = ""
net = None; online_ready = False
scroll_y = 0
scroll_classement = 0  # === AJOUT : scroll pour le classement ===
particles = [[random.randint(0, LARGEUR), random.randint(0, HAUTEUR), random.randint(1, 3)] for _ in range(70)]

# BOUTONS
btn_to_login = Bouton(300, 220, 300, 70, "SE CONNECTER")
btn_to_register = Bouton(300, 320, 300, 70, "S'INSCRIRE")
btn_play = Bouton(300, 200, 300, 55, "JOUER", color=(50, 160, 80))
btn_stats = Bouton(300, 270, 300, 55, "STATISTIQUES", color=(180, 130, 20))
btn_classement = Bouton(300, 340, 300, 55, "CLASSEMENT", color=(160, 32, 240))  # === AJOUT ===
btn_settings = Bouton(300, 410, 300, 55, "PARAMETRES", color=(70, 130, 255))
btn_quit = Bouton(300, 480, 300, 55, "QUITTER", color=(220, 60, 60))
btn_back = Bouton(20, 20, 160, 50, "RETOUR")
btn_solo = Bouton(300, 180, 300, 70, "1 JOUEUR (IA)", color=(40, 40, 60))
btn_pvp = Bouton(300, 270, 300, 70, "2 JOUEURS (LOCAL)", color=GRIS)
btn_online = Bouton(300, 360, 300, 70, "EN LIGNE", color=(100, 60, 200))
btn_logout = Bouton(300, 250, 300, 70, "DECONNEXION", color=(180, 50, 50))
btn_yes = Bouton(250, 330, 150, 60, "OUI", color=(50, 150, 50))
btn_no = Bouton(500, 330, 150, 60, "NON", color=(150, 50, 50))
btn_shop = Bouton(20, 150, 70, 70, "", color=(120, 60, 180), is_shop=True)

def reset_game():
    global p1, p2, game_timer, last_timer_sec, online_ready
    u_data = load_user(current_user)
    skin_actuel = u_data.get("equipped_skin", "Basique")
    
    p1 = Joueur(100, 300, skin_actuel, {"gauche":pygame.K_a,"droite":pygame.K_d,"haut":pygame.K_w,"bas":pygame.K_s}, current_user)
    
    if game_mode == 3:
        p2 = Joueur(700, 300, "Basique", {}, "Recherche...")
        online_ready = False
    else:
        nom_p2 = "IA" if game_mode == 1 else "Joueur 2"
        ctrl_p2 = {} if game_mode == 1 else {"gauche":pygame.K_LEFT,"droite":pygame.K_RIGHT,"haut":pygame.K_UP,"bas":pygame.K_DOWN}
        p2 = Joueur(700, 300, "Basique", ctrl_p2, nom_p2)
        if game_mode == 1: p2.couleur = ROUGE
    
    p1.classe, p2.classe, game_timer, last_timer_sec = "attaque", "fugueur", 15000, 15

# === AJOUT : Médailles pour le top 3 ===
MEDAILLES = {1: ("🥇", OR), 2: ("🥈", (192, 192, 192)), 3: ("🥉", (205, 127, 50))}

# BOUCLE PRINCIPALE
while True:
    dt = clock.tick(60)
    fenetre.fill(FOND)
    
    for p in particles:
        p[1] += p[2]
        if p[1] > HAUTEUR: p[1] = 0; p[0] = random.randint(0, LARGEUR)
        pygame.draw.circle(fenetre, (80, 80, 120), (p[0], p[1]), 2)

    events = pygame.event.get()
    for e in events:
        if e.type == pygame.QUIT: pygame.quit(); sys.exit()
        
        if etat == AUTH:
            if btn_to_login.click(e): etat = LOGIN; input_text, pwd_buffer, error_text, input_mode = "", "", "", "name"
            if btn_to_register.click(e): etat = REGISTER; input_text, pwd_buffer, error_text, input_mode = "", "", "", "name"
        
        elif etat in [LOGIN, REGISTER]:
            if btn_back.click(e): etat = AUTH
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_BACKSPACE:
                    if input_mode == "pwd": pwd_buffer = pwd_buffer[:-1]
                    else: input_text = input_text[:-1]
                elif e.key == pygame.K_RETURN:
                    if input_mode == "name":
                        temp_name = input_text.strip()
                        if temp_name: input_mode = "pwd"
                    else:
                        if etat == LOGIN:
                            if login_user(temp_name, pwd_buffer): current_user = temp_name; etat = MENU; snd_success.play()
                            else: error_text = "Erreur: Verifiez vos infos"; snd_error.play()
                        else:
                            if create_user(temp_name, pwd_buffer): current_user = temp_name; etat = MENU; snd_success.play()
                            else: error_text = "Nom d'Utilisateur deja pris"; snd_error.play()
                else:
                    if len(e.unicode) > 0 and e.key not in [pygame.K_ESCAPE, pygame.K_TAB, pygame.K_RETURN, pygame.K_BACKSPACE]:
                        if input_mode == "pwd": pwd_buffer += e.unicode
                        else: input_text += e.unicode

        elif etat == MENU:
            if btn_play.click(e): etat = JEU_MODE
            if btn_stats.click(e): etat = STATS
            if btn_classement.click(e): etat = CLASSEMENT; scroll_classement = 0  # === AJOUT ===
            if btn_settings.click(e): etat = SETTINGS
            if btn_shop.click(e): etat = SHOP; scroll_y = 0
            if btn_quit.click(e): pygame.quit(); sys.exit()

        elif etat == SHOP:
            if btn_back.click(e): etat = MENU
            u_data = load_user(current_user)
            if e.type == pygame.MOUSEWHEEL:
                scroll_y += e.y * 30
                min_scroll = min(0, (HAUTEUR - 200) - (len(SKINS_DATA) * 55) - 20)
                scroll_y = max(min_scroll, min(0, scroll_y))
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1: 
                for i, (name, info) in enumerate(SKINS_DATA.items()):
                    rect_item = pygame.Rect(100, 200 + i*55 + scroll_y, 700, 50)
                    if rect_item.collidepoint(e.pos):
                        if name in u_data["owned_skins"]:
                            u_data["equipped_skin"] = name; snd_success.play()
                        elif u_data["money"] >= info[2]:
                            u_data["money"] -= info[2]; u_data["owned_skins"].append(name); snd_success.play()
                        else: snd_error.play()
                        save_user(current_user, u_data)

        elif etat == JEU_MODE:
            if btn_back.click(e): etat = MENU
            if btn_solo.click(e): game_mode = 1; reset_game(); etat = JEU_COMBAT
            if btn_pvp.click(e): game_mode = 2; reset_game(); etat = JEU_COMBAT
            if btn_online.click(e):
                game_mode = 3; reset_game(); etat = SEARCHING
                net = Network()
                if not net.connect():
                    threading.Thread(target=server_thread, daemon=True).start()
                    pygame.time.delay(500) 
                    net.connect()

        elif etat == STATS:
            if btn_back.click(e): etat = MENU

        elif etat == SETTINGS:
            if btn_back.click(e): etat = MENU
            if btn_logout.click(e): etat = CONFIRM

        elif etat == CONFIRM:
            if btn_yes.click(e): current_user = None; etat = AUTH
            if btn_no.click(e): etat = SETTINGS

        elif etat == SEARCHING:
            if btn_back.click(e): etat = JEU_MODE

        # === AJOUT : Gestion scroll du classement ===
        elif etat == CLASSEMENT:
            if btn_back.click(e): etat = MENU
            if e.type == pygame.MOUSEWHEEL:
                scroll_classement += e.y * 30
                nb_joueurs = len(load_all_users())
                min_scroll = min(0, (HAUTEUR - 200) - nb_joueurs * 52 - 20)
                scroll_classement = max(min_scroll, min(0, scroll_classement))

        elif etat == FIN:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                etat = MENU

    # ========== AFFICHAGE ==========

    if etat == SEARCHING:
        txt_search = font.render("RECHERCHE D'UN ADVERSAIRE...", True, JAUNE)
        fenetre.blit(txt_search, (LARGEUR//2 - txt_search.get_width()//2, HAUTEUR//2))
        btn_back.draw(fenetre)
        
        u_data = load_user(current_user)
        my_data = {"nom": current_user, "x": p1.rect.x, "y": p1.rect.y, "skin": u_data["equipped_skin"], "vies": p1.vies, "classe": p1.classe}
        reply = net.send(my_data)
        
        other_id = "1" if net.p_id == 0 else "0"
        if reply and reply.get(other_id):
            p2.nom = reply[other_id]["nom"]
            p2.update_skin(reply[other_id]["skin"])
            online_ready = True
            etat = JEU_COMBAT

    elif etat == JEU_COMBAT:
        game_timer -= dt
        curr_sec = math.ceil(game_timer / 1000)
        if curr_sec <= 3 and curr_sec != last_timer_sec and curr_sec > 0: snd_tick.play()
        last_timer_sec = curr_sec
        
        p1.move()
        
        if game_mode == 1:
            v_ia = 4; zone_ia = pygame.Rect(51, 51, LARGEUR - 102, HAUTEUR - 102)
            dx = (v_ia if p2.rect.x < p1.rect.x else -v_ia) * (1 if p2.classe == "attaque" else -1)
            dy = (v_ia if p2.rect.y < p1.rect.y else -v_ia) * (1 if p2.classe == "attaque" else -1)
            p2.rect.x += dx; p2.rect.y += dy; p2.rect.clamp_ip(zone_ia)
        elif game_mode == 2:
            p2.move()
        elif game_mode == 3:
            u_data = load_user(current_user)
            my_data = {"nom": current_user, "x": p1.rect.x, "y": p1.rect.y, "skin": u_data["equipped_skin"], "vies": p1.vies, "classe": p1.classe}
            reply = net.send(my_data)
            other_id = "1" if net.p_id == 0 else "0"
            if reply and reply.get(other_id):
                p2.rect.x = reply[other_id]["x"]
                p2.rect.y = reply[other_id]["y"]
                p2.vies = reply[other_id]["vies"]
                p2.classe = reply[other_id]["classe"]

        if p1.rect.colliderect(p2.rect):
            now = pygame.time.get_ticks()
            if p1.classe == "attaque" and now - p1.last_attack > 800: p2.vies -= 1; p1.last_attack = now
            elif p2.classe == "attaque" and now - p2.last_attack > 800: p1.vies -= 1; p2.last_attack = now
            
        if game_timer <= 0:
            game_timer = 15000
            p1.classe, p2.classe = p2.classe, p1.classe
            
        p1.draw(fenetre); p2.draw(fenetre)
        
        if curr_sec <= 3:
            t_surf = font_timer.render(str(curr_sec), True, JAUNE if curr_sec > 1 else ROUGE)
            fenetre.blit(t_surf, (LARGEUR//2-30, HAUTEUR//2-100))
        
        fenetre.blit(font_small.render(f"{p1.nom} [{p1.classe.upper()}]", True, BLEU), (20, 80))
        fenetre.blit(font_small.render(f"{p2.nom} [{p2.classe.upper()}]", True, ROUGE), (LARGEUR-220, 80))
        
        if p1.vies <= 0 or p2.vies <= 0:
            gagnant = p1.nom if p2.vies <= 0 else p2.nom
            if game_mode != 3:
                if p2.vies <= 0:  # Joueur 1 gagne
                    d = load_user(current_user)
                    d["wins"] += 1
                    d["money"] += 100
                    save_user(current_user, d)
                else:  # === AJOUT : compter les défaites ===
                    d = load_user(current_user)
                    d["losses"] = d.get("losses", 0) + 1
                    save_user(current_user, d)
            etat = FIN

    elif etat == AUTH:
        txt = font_big.render("FIGHTING PIT", True, JAUNE)
        fenetre.blit(txt, (LARGEUR//2 - txt.get_width()//2, 80))
        btn_to_login.draw(fenetre); btn_to_register.draw(fenetre)

    elif etat in [LOGIN, REGISTER]:
        btn_back.draw(fenetre)
        titre = font.render("CONNEXION" if etat == LOGIN else "INSCRIPTION", True, BLANC)
        fenetre.blit(titre, (LARGEUR//2 - titre.get_width()//2, 100))
        lbl = "Nom d'utilisateur" if input_mode == "name" else "Mot de passe (Appuyez sur Entrée)"
        fenetre.blit(font_small.render(lbl, True, JAUNE), (250, 210))
        pygame.draw.rect(fenetre, GRIS, (250, 240, 400, 50), border_radius=10)
        disp = input_text if input_mode == "name" else ("*" * len(pwd_buffer))
        fenetre.blit(font.render(disp, True, BLANC), (260, 250))
        if error_text: fenetre.blit(font_small.render(error_text, True, ROUGE), (LARGEUR//2-100, 320))

    elif etat == MENU:
        u_data = load_user(current_user)
        wins = u_data.get("wins", 0) if u_data else 0
        r_name, r_lvl, r_col = get_rank_info(wins)
        welcome = font_big.render(current_user, True, BLANC)
        fenetre.blit(welcome, (LARGEUR//2 - welcome.get_width()//2, 90))
        rank_txt = font.render(f"{r_name} (Rang {r_lvl})", True, r_col)
        fenetre.blit(rank_txt, (LARGEUR//2 - rank_txt.get_width()//2, 160))
        btn_play.draw(fenetre); btn_stats.draw(fenetre); btn_classement.draw(fenetre)
        btn_settings.draw(fenetre); btn_quit.draw(fenetre)
        btn_shop.draw(fenetre)

    elif etat == SHOP:
        btn_back.draw(fenetre)
        titre_shop = font_big.render("BOUTIQUE", True, (120, 60, 180))
        fenetre.blit(titre_shop, (LARGEUR//2 - titre_shop.get_width()//2, 80))
        u_data = load_user(current_user)
        money = u_data.get("money", 0) if u_data else 0
        fenetre.blit(font.render(f"Argent : {money} $", True, (100, 255, 100)), (LARGEUR//2-80, 150))
        fenetre.set_clip(pygame.Rect(0, 190, LARGEUR, HAUTEUR - 190))
        for i, (name, info) in enumerate(SKINS_DATA.items()):
            rect_item = pygame.Rect(100, 200 + i*55 + scroll_y, 700, 50)
            survol = rect_item.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(fenetre, (40, 40, 80) if survol else (30, 30, 50), rect_item, border_radius=10)
            pygame.draw.rect(fenetre, BLANC, rect_item, 1, border_radius=10)
            pygame.draw.rect(fenetre, info[0], (120, 210 + i*55 + scroll_y, 30, 30), border_radius=5)
            pygame.draw.rect(fenetre, info[1], (120, 210 + i*55 + scroll_y, 30, 30), 2, border_radius=5)
            fenetre.blit(font.render(name, True, BLANC), (170, 212 + i*55 + scroll_y))
            if name == u_data["equipped_skin"]: lbl, col = "ÉQUIPÉ", JAUNE
            elif name in u_data["owned_skins"]: lbl, col = "ÉQUIPER", VERT
            else: lbl, col = f"{info[2]} $", BLANC
            txt_s = font.render(lbl, True, col)
            fenetre.blit(txt_s, (LARGEUR - 250, 212 + i*55 + scroll_y))
        fenetre.set_clip(None)

    elif etat == STATS:
        btn_back.draw(fenetre)
        u_data = load_user(current_user)
        wins = u_data.get("wins", 0); losses = u_data.get("losses", 0); money = u_data.get("money", 0)
        r_name, r_lvl, r_col = get_rank_info(wins)
        titre_s = font_big.render("STATISTIQUES", True, OR)
        fenetre.blit(titre_s, (LARGEUR//2 - titre_s.get_width()//2, 100))
        fenetre.blit(font.render(f"Victoires : {wins}", True, VERT), (LARGEUR//2-100, 230))
        # === AJOUT : afficher les défaites et le ratio ===
        fenetre.blit(font.render(f"Défaites  : {losses}", True, ROUGE), (LARGEUR//2-100, 280))
        ratio = f"{wins/(wins+losses)*100:.1f}%" if (wins + losses) > 0 else "N/A"
        fenetre.blit(font.render(f"Ratio V/D : {ratio}", True, BLANC), (LARGEUR//2-100, 330))
        fenetre.blit(font.render(f"Niveau    : {r_lvl} - {r_name}", True, r_col), (LARGEUR//2-100, 380))
        fenetre.blit(font.render(f"Argent    : {money} $", True, (100, 255, 100)), (LARGEUR//2-100, 430))

    elif etat == SETTINGS:
        btn_back.draw(fenetre)
        titre_set = font_big.render("PARAMETRES", True, BLEU)
        fenetre.blit(titre_set, (LARGEUR//2 - titre_set.get_width()//2, 100))
        btn_logout.draw(fenetre)

    elif etat == CONFIRM:
        pygame.draw.rect(fenetre, GRIS, (200, 180, 500, 260), border_radius=20)
        pygame.draw.rect(fenetre, BLANC, (200, 180, 500, 260), 2, border_radius=20)
        txt_confirm = font.render("Voulez-vous vous déconnecter ?", True, BLANC)
        fenetre.blit(txt_confirm, (LARGEUR//2 - txt_confirm.get_width()//2, 240))
        btn_yes.draw(fenetre); btn_no.draw(fenetre)

    elif etat == FIN:
        txt = font_big.render(f"VICTOIRE : {gagnant}", True, JAUNE)
        fenetre.blit(txt, (LARGEUR//2 - txt.get_width()//2, 250))
        if gagnant == current_user:
            fenetre.blit(font.render("+ 100 $ | + 1 Victoire", True, (100, 255, 100)), (LARGEUR//2-120, 330))
        else:
            fenetre.blit(font.render("+ 1 Défaite", True, ROUGE), (LARGEUR//2-60, 330))
        fenetre.blit(font.render("Appuyez sur R pour le menu", True, BLANC), (LARGEUR//2-170, 400))

    elif etat == JEU_MODE:
        btn_back.draw(fenetre); btn_solo.draw(fenetre); btn_pvp.draw(fenetre); btn_online.draw(fenetre)

    # === AJOUT : Écran CLASSEMENT ===
    elif etat == CLASSEMENT:
        btn_back.draw(fenetre)

        # Titre
        titre_c = font_big.render("CLASSEMENT", True, MAUVE)
        fenetre.blit(titre_c, (LARGEUR//2 - titre_c.get_width()//2, 30))

        # En-têtes colonnes
        fenetre.blit(font_small.render("#", True, JAUNE), (60, 130))
        fenetre.blit(font_small.render("Joueur", True, JAUNE), (110, 130))
        fenetre.blit(font_small.render("Rang", True, JAUNE), (380, 130))
        fenetre.blit(font_small.render("Victoires", True, JAUNE), (560, 130))
        fenetre.blit(font_small.render("Défaites", True, JAUNE), (680, 130))
        fenetre.blit(font_small.render("Ratio", True, JAUNE), (790, 130))
        pygame.draw.line(fenetre, GRIS, (50, 155), (LARGEUR - 50, 155), 1)

        # Zone scrollable
        fenetre.set_clip(pygame.Rect(0, 158, LARGEUR, HAUTEUR - 158))

        joueurs = load_all_users()
        for i, j in enumerate(joueurs):
            position = i + 1
            y = 165 + i * 52 + scroll_classement

            # Fond surbrillance joueur actuel
            is_me = (j["nom"] == current_user)
            bg_col = (50, 30, 80) if is_me else ((35, 35, 55) if i % 2 == 0 else (25, 25, 40))
            pygame.draw.rect(fenetre, bg_col, (50, y, LARGEUR - 100, 46), border_radius=8)
            if is_me:
                pygame.draw.rect(fenetre, MAUVE, (50, y, LARGEUR - 100, 46), 1, border_radius=8)

            # Rang (position dans le classement)
            if position <= 3:
                med_col = [OR, (192, 192, 192), (205, 127, 50)][position - 1]
                pos_txt = font.render(str(position), True, med_col)
            else:
                pos_txt = font_small.render(str(position), True, (150, 150, 180))
            fenetre.blit(pos_txt, (60, y + 10))

            # Nom
            nom_col = MAUVE if is_me else BLANC
            fenetre.blit(font_small.render(j["nom"], True, nom_col), (110, y + 13))

            # Rang de jeu (couleur selon victoires)
            r_name, r_lvl, r_col = get_rank_info(j["wins"])
            rang_txt = font_small.render(f"Lv{r_lvl} {r_name}", True, r_col)
            fenetre.blit(rang_txt, (380, y + 13))

            # Victoires
            fenetre.blit(font_small.render(str(j["wins"]), True, VERT), (590, y + 13))

            # Défaites
            fenetre.blit(font_small.render(str(j["losses"]), True, ROUGE), (710, y + 13))

            # Ratio
            total = j["wins"] + j["losses"]
            ratio_str = f"{j['wins']/total*100:.0f}%" if total > 0 else "-"
            fenetre.blit(font_small.render(ratio_str, True, BLANC), (800, y + 13))

        if not joueurs:
            msg = font.render("Aucun joueur enregistré.", True, GRIS)
            fenetre.blit(msg, (LARGEUR//2 - msg.get_width()//2, 280))

        fenetre.set_clip(None)

    pygame.display.flip()