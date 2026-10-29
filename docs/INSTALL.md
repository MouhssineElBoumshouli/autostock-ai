# Installer AutoStock dans un magasin · Install AutoStock in a shop

[Français](#français) · [English](#english)

---

## Français

AutoStock tourne sur **un seul PC du magasin**. Les autres ordinateurs et les téléphones l'ouvrent dans leur navigateur, sur le même réseau (Wi-Fi ou câble). Rien n'est envoyé sur Internet.

Toutes les commandes se tapent dans **PowerShell**, ouvert dans le dossier AutoStock (dans l'Explorateur : ouvrir le dossier, cliquer dans la barre d'adresse, taper `powershell`, Entrée).

### 1. Le PC qu'il faut
- Windows 10 ou 11, 64 bits.
- 8 Go de mémoire (16 Go pour l'assistant IA). 20 Go libres sur le disque.
- Il reste allumé pendant les heures d'ouverture. Réglez la mise en veille sur « Jamais » quand il est branché.

### 2. Installer Docker Desktop (une seule fois)
1. Téléchargez Docker Desktop sur https://www.docker.com/products/docker-desktop et installez-le. Laissez cochée l'option **WSL 2**. Redémarrez le PC si on vous le demande.
2. Ouvrez Docker Desktop, acceptez les conditions, attendez « Engine running ».
3. Dans Docker Desktop : **Settings → General → cocher « Start Docker Desktop when you sign in »**. Ainsi AutoStock redémarre tout seul après une coupure de courant, dès que quelqu'un ouvre la session Windows.

### 3. Décompresser AutoStock
Décompressez le zip dans `C:\AutoStock` (par exemple). Ce dossier contient le programme. Vos données sont gardées par Docker, à part : le dossier peut être remplacé à chaque mise à jour.

### 4. Créer le fichier `.env`
1. Dans le dossier AutoStock : `copy .env.example .env` puis `notepad .env`.
2. Remplacez `POSTGRES_PASSWORD=change-me` par un mot de passe fort (16 caractères au moins). Pour en fabriquer un, tapez dans PowerShell :
   ```
   -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 | % {[char]$_})
   ```
   Copiez le résultat après `POSTGRES_PASSWORD=`. Notez-le sur papier, rangé en lieu sûr. **Ne le changez plus ensuite** : la base de données garde le mot de passe de sa création.
3. Ligne `APP_URL` : enlevez le `#` et mettez les adresses du PC (étape 7). Pour commencer : `APP_URL=http://localhost:8080`.
4. Enregistrez. AutoStock refuse de démarrer avec un mot de passe faible et dit pourquoi.

### 5. Démarrer
```
docker compose -f docker-compose.prod.yml up -d --build
```
La première fois prend quelques minutes (téléchargements). Ensuite, AutoStock démarre tout seul avec Windows.

### 6. Premier réglage
Sur le PC du magasin, ouvrez **http://localhost:8080**. Entrez le nom du magasin, votre nom, votre email et un mot de passe : vous devenez le propriétaire. Ajoutez votre équipe dans **Équipe**.

### 7. Ouvrir AutoStock depuis les autres ordinateurs et téléphones
1. Sur le PC du magasin : `ipconfig` → notez l'**Adresse IPv4** (par exemple `192.168.1.20`). `hostname` → le nom du PC (par exemple `COMPTOIR-PC`).
2. Dans `.env` : `APP_URL=http://localhost:8080,http://192.168.1.20:8080,http://COMPTOIR-PC:8080`, puis relancez la commande de l'étape 5.
3. Ouvrez le port dans le pare-feu Windows (PowerShell **en administrateur**, une seule fois) :
   ```
   New-NetFirewallRule -DisplayName "AutoStock" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private
   ```
   Le réseau du magasin doit être en « Privé » (Paramètres → Réseau et Internet → votre réseau).
4. Les employés ouvrent `http://192.168.1.20:8080` (ou `http://COMPTOIR-PC:8080`). Si l'adresse IPv4 change après un redémarrage de la box, demandez à votre installateur de la fixer dans la box, ou utilisez le nom du PC.

### 8. Sauvegardes
- Chaque jour à **02:00**, et au démarrage si la dernière date de plus de 24 h (PC éteint la nuit), AutoStock fait une sauvegarde dans le dossier **`backups`**, à côté du programme : `autostock-2026-10-29.dump`. Il garde les 14 derniers jours et 1 par mois pendant 12 mois. Une sauvegarde ne compte qu'une fois relue et vérifiée.
- **Paramètres** montre la dernière sauvegarde. Sans sauvegarde depuis 2 jours, le propriétaire voit « À traiter » sur l'Accueil.
- **Une fois par semaine, copiez le dossier `backups` sur une clé USB ou un espace en ligne** (Google Drive, OneDrive…). Une sauvegarde sur le même disque disparaît avec le disque.
- Une sauvegarde tout de suite : `docker compose -f docker-compose.prod.yml exec backup backup.sh make autostock-maintenant`

### 9. Restaurer une sauvegarde
Remettez le fichier voulu dans le dossier `backups`, puis :
```
docker compose -f docker-compose.prod.yml run --rm app python -m app.restore autostock-2026-10-29.dump
```
AutoStock sauvegarde d'abord les données actuelles (`autostock-before-restore-....dump`), restaure, applique les changements de cette version et affiche le nombre de lignes des tableaux principaux. Si le fichier est illisible, rien n'est changé. Les employés voient une erreur pendant quelques secondes.

### 10. Mettre à jour
1. `docker compose -f docker-compose.prod.yml stop`
2. Renommez l'ancien dossier (`C:\AutoStock-ancien`), décompressez la nouvelle version dans `C:\AutoStock`.
3. Copiez **`.env`** et le dossier **`backups`** de l'ancien dossier dans le nouveau. Rien d'autre : les données sont dans Docker, pas dans le dossier.
4. `docker compose -f docker-compose.prod.yml up -d --build`

Si la base doit changer, AutoStock fait d'abord une sauvegarde (`autostock-before-update-....dump`). Si le changement échoue, rien n'est perdu : AutoStock ne démarre pas et la page http://localhost:8080 dit quoi faire (remettre l'ancien dossier et, seulement si besoin, quelle sauvegarde restaurer). Gardez l'ancien dossier une semaine.

### 11. Mot de passe oublié
```
docker compose -f docker-compose.prod.yml exec app python -m app.reset_password proprietaire@magasin.ma
```
Tapez le nouveau mot de passe deux fois (rien ne s'affiche, c'est normal). La personne est déconnectée partout ; la page Activité le note.

### 12. Activer l'assistant IA (facultatif, gratuit, sur ce PC)
Avec une carte graphique NVIDIA : `docker compose -f docker-compose.prod.yml --profile ai-gpu up -d`. Sans : `--profile ai` (plus lent). Environ 2,5 Go téléchargés une fois. Sans IA, la page Demander marche quand même avec des mots simples.

### 13. « Ça ne démarre pas »
- Docker Desktop est-il ouvert (« Engine running ») ? Ouvrez-le, attendez une minute.
- `docker compose -f docker-compose.prod.yml ps` : chaque ligne doit dire « Up ». Sinon : `docker compose -f docker-compose.prod.yml logs app` (ou `logs db`, `logs backup`) et lisez les dernières lignes.
- « POSTGRES_PASSWORD … missing or too weak » : refaites l'étape 4.
- Port 8080 déjà pris : `APP_PORT=8090` dans `.env` (et `:8090` dans `APP_URL`), puis l'étape 5.
- « This request did not come from the AutoStock website » : l'adresse tapée dans le navigateur doit être dans `APP_URL`.
- La page dit « AutoStock could not update » : suivez ce qu'elle dit (étape 10).
- Disque plein : Paramètres le dit ; libérez de la place, copiez les vieilles sauvegardes ailleurs.

---

## English

AutoStock runs on **one PC in the shop**. The other computers and phones open it in their browser, on the same network (Wi-Fi or cable). Nothing is sent to the internet.

Type every command in **PowerShell**, opened in the AutoStock folder (in Explorer: open the folder, click the address bar, type `powershell`, Enter).

### 1. The PC you need
- Windows 10 or 11, 64-bit.
- 8 GB of memory (16 GB for the AI assistant). 20 GB free on the disk.
- It stays on during opening hours. Set sleep to "Never" when plugged in.

### 2. Install Docker Desktop (once)
1. Download Docker Desktop from https://www.docker.com/products/docker-desktop and install it. Keep **WSL 2** ticked. Restart the PC if asked.
2. Open Docker Desktop, accept the terms, wait for "Engine running".
3. In Docker Desktop: **Settings → General → tick "Start Docker Desktop when you sign in"**. AutoStock then comes back by itself after a power cut, as soon as someone signs in to Windows.

### 3. Unzip AutoStock
Unzip it into `C:\AutoStock` (for example). This folder is the program. Your data is kept by Docker, separately: the folder can be replaced at every update.

### 4. Create the `.env` file
1. In the AutoStock folder: `copy .env.example .env` then `notepad .env`.
2. Replace `POSTGRES_PASSWORD=change-me` with a strong password (16 characters or more). To make one, type in PowerShell:
   ```
   -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 | % {[char]$_})
   ```
   Paste the result after `POSTGRES_PASSWORD=`. Write it on paper, kept somewhere safe. **Never change it afterwards**: the database keeps the password it was created with.
3. The `APP_URL` line: remove the `#` and put the PC's addresses (step 7). To start: `APP_URL=http://localhost:8080`.
4. Save. AutoStock refuses to start with a weak password and says why.

### 5. Start
```
docker compose -f docker-compose.prod.yml up -d --build
```
The first time takes a few minutes (downloads). After that, AutoStock starts by itself with Windows.

### 6. First setup
On the shop PC, open **http://localhost:8080**. Enter the shop name, your name, email and a password: you become the owner. Add your team on **Team**.

### 7. Open AutoStock from the other computers and phones
1. On the shop PC: `ipconfig` → note the **IPv4 Address** (for example `192.168.1.20`). `hostname` → the PC's name (for example `COMPTOIR-PC`).
2. In `.env`: `APP_URL=http://localhost:8080,http://192.168.1.20:8080,http://COMPTOIR-PC:8080`, then run the step 5 command again.
3. Allow the port in Windows Firewall (PowerShell **as administrator**, once):
   ```
   New-NetFirewallRule -DisplayName "AutoStock" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private
   ```
   The shop network must be "Private" (Settings → Network & internet → your network).
4. Employees open `http://192.168.1.20:8080` (or `http://COMPTOIR-PC:8080`). If the IPv4 address changes after the router restarts, ask your installer to fix it in the router, or use the PC's name.

### 8. Backups
- Every day at **02:00**, and at start if the last one is older than 24 hours (PC off at night), AutoStock saves a backup in the **`backups`** folder next to the program: `autostock-2026-10-29.dump`. It keeps the last 14 days and 1 per month for 12 months. A backup only counts once it has been read back and checked.
- **Settings** shows the last backup. With no backup for 2 days, the owner sees "Needs action" on Today.
- **Once a week, copy the `backups` folder to a USB stick or a cloud drive** (Google Drive, OneDrive…). A backup on the same disk is lost with the disk.
- A backup right now: `docker compose -f docker-compose.prod.yml exec backup backup.sh make autostock-now`

### 9. Restore a backup
Put the file you want in the `backups` folder, then:
```
docker compose -f docker-compose.prod.yml run --rm app python -m app.restore autostock-2026-10-29.dump
```
AutoStock first backs up the current data (`autostock-before-restore-....dump`), restores, applies this version's changes and prints the row count of the main tables. If the file can't be read, nothing is changed. Employees see an error for a few seconds.

### 10. Update
1. `docker compose -f docker-compose.prod.yml stop`
2. Rename the old folder (`C:\AutoStock-old`), unzip the new version into `C:\AutoStock`.
3. Copy **`.env`** and the **`backups`** folder from the old folder into the new one. Nothing else: the data is in Docker, not in the folder.
4. `docker compose -f docker-compose.prod.yml up -d --build`

If the database must change, AutoStock backs it up first (`autostock-before-update-....dump`). If the change fails, nothing is lost: AutoStock does not start, and the page at http://localhost:8080 says what to do (put the old folder back and, only if needed, which backup to restore). Keep the old folder for a week.

### 11. Forgotten password
```
docker compose -f docker-compose.prod.yml exec app python -m app.reset_password owner@shop.ma
```
Type the new password twice (nothing is shown, that's normal). The person is logged out everywhere; the Activity page shows it.

### 12. Turn on the AI assistant (optional, free, on this PC)
With an NVIDIA graphics card: `docker compose -f docker-compose.prod.yml --profile ai-gpu up -d`. Without: `--profile ai` (slower). About 2.5 GB downloaded once. Without AI, the Ask page still works with simple words.

### 13. "It doesn't start"
- Is Docker Desktop open ("Engine running")? Open it, wait a minute.
- `docker compose -f docker-compose.prod.yml ps`: every line should say "Up". If not: `docker compose -f docker-compose.prod.yml logs app` (or `logs db`, `logs backup`) and read the last lines.
- "POSTGRES_PASSWORD … missing or too weak": do step 4 again.
- Port 8080 already used: `APP_PORT=8090` in `.env` (and `:8090` in `APP_URL`), then step 5.
- "This request did not come from the AutoStock website": the address in the browser bar must be in `APP_URL`.
- The page says "AutoStock could not update": do what it says (step 10).
- Disk full: Settings says so; free some space, copy old backups elsewhere.
