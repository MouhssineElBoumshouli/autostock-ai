# Installer AutoStock dans un magasin · Install AutoStock in a shop

[Français](#français) · [English](#english)

---

## Français

### L'application Windows (recommandé)

AutoStock s'installe comme un programme normal. Pas de Docker, pas de commande à taper, et **tout marche sans Internet**.

1. **Installer.** Double-cliquez sur `AutoStock-Setup.exe`. Si Windows affiche « Windows a protégé votre ordinateur », cliquez sur **Informations complémentaires**, puis **Exécuter quand même** (ce message vient du fait que le programme n'est pas encore signé). Cliquez sur **Suivant** jusqu'à la fin. Aucun mot de passe administrateur n'est demandé.
2. **Ouvrir.** Double-cliquez sur l'icône **AutoStock AI** du bureau. AutoStock s'ouvre dans sa propre fenêtre. La première fois, il crée la base de données du magasin (quelques secondes), puis demande le nom du magasin et le compte du propriétaire.
3. **Les autres ordinateurs et téléphones du magasin.** Sur le même Wi-Fi, ouvrez le navigateur et tapez `http://NOM-DU-PC:8765` (le nom du PC est dans Paramètres Windows > Système > Informations système). La première fois, Windows demande d'autoriser AutoStock sur le réseau : cliquez sur **Autoriser** (réseaux privés).
4. **Fermer la fenêtre n'arrête pas AutoStock**, pour que les autres appareils continuent à l'utiliser. Il démarre aussi tout seul avec Windows. Pour l'arrêter : menu Démarrer > **Stop AutoStock**.
5. **Sauvegardes.** Une par jour, toute seule, dans `Documents\AutoStock backups` (les 14 derniers jours et 1 par mois pendant 12 mois). Copiez ce dossier sur une clé USB de temps en temps.
6. **Restaurer une sauvegarde.** Fermez AutoStock (Stop AutoStock), puis dans PowerShell : `& "$env:LOCALAPPDATA\Programs\AutoStock\AutoStock.exe" --restore autostock-2026-10-29.dump`
7. **Mettre à jour.** Lancez le nouveau `AutoStock-Setup.exe`. Les données du magasin ne sont jamais touchées, et une sauvegarde est faite avant chaque changement de la base de données.
8. **Où sont les données ?** `%LOCALAPPDATA%\AutoStock` (base de données, réglages, journaux). La désinstallation ne les supprime pas.
9. **L'assistant en ligne de « Questions » (facultatif).** Ouvrez `%LOCALAPPDATA%\AutoStock\settings.env` avec le Bloc-notes, collez votre clé Groq après `GROQ_API_KEY=`, enregistrez, puis Stop AutoStock et rouvrez-le.

### Avec Docker (pour les développeurs)

AutoStock tourne sur **un seul PC du magasin**. Les autres ordinateurs et les téléphones l'ouvrent dans leur navigateur, sur le même réseau (Wi-Fi ou câble). Rien n'est envoyé sur Internet, sauf si vous activez l'écriture Groq dans Paramètres.

Toutes les commandes se tapent dans **PowerShell**, ouvert dans le dossier AutoStock (dans l'Explorateur : ouvrir le dossier, cliquer dans la barre d'adresse, taper `powershell`, Entrée).

### 1. Le PC qu'il faut
- Windows 10 ou 11, 64 bits.
- 8 Go de mémoire (16 Go pour l'assistant IA). 20 Go libres sur le disque.
- Il reste allumé pendant les heures d'ouverture. Réglez la mise en veille sur « Jamais » quand il est branché.

### 2. Installer Docker Desktop (une seule fois)
1. Téléchargez Docker Desktop sur https://www.docker.com/products/docker-desktop et installez-le. Laissez cochée l'option **WSL 2**. Redémarrez le PC si on vous le demande.
2. Ouvrez Docker Desktop, acceptez les conditions, attendez « Engine running ».
3. Dans Docker Desktop : **Settings → General → cocher « Start Docker Desktop when you sign in »**. Ainsi AutoStock redémarre tout seul après une coupure de courant, dès que quelqu'un ouvre la session Windows.
4. **PC de 8 Go seulement : donnez 5 Go de mémoire à Docker.** Sinon Docker n'en prend que la moitié (4 Go), trop peu pour un grand magasin pendant le calcul des prévisions de la nuit. Docker Desktop n'a pas de réglage pour cela avec WSL 2 (Settings → Resources dit que Windows s'en occupe) : on le règle dans un fichier.
   1. Dans PowerShell : `notepad "$env:USERPROFILE\.wslconfig"` (Bloc-notes propose de créer le fichier : **Oui**).
   2. Écrivez ces deux lignes, puis enregistrez :
      ```
      [wsl2]
      memory=5GB
      ```
   3. Quittez Docker Desktop (icône près de l'horloge → **Quit Docker Desktop**), tapez `wsl --shutdown` dans PowerShell, puis rouvrez Docker Desktop.
   4. Pour vérifier : `docker info --format "{{.MemTotal}}"` affiche environ 5 milliards (5 Go).

   Avec 16 Go ou plus, rien à faire.

### 3. Décompresser AutoStock
Décompressez le zip dans `C:\AutoStock` (par exemple). Ce dossier contient le programme. Vos données sont gardées par Docker, à part : le dossier peut être remplacé à chaque mise à jour.

### 4. Créer le fichier `.env`
1. Dans le dossier AutoStock : `copy .env.example .env` puis `notepad .env`.
2. Remplacez `POSTGRES_PASSWORD=change-me` par un mot de passe fort (16 caractères au moins). Pour en fabriquer un, tapez dans PowerShell :
   ```
   -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 | % {[char]$_})
   ```
   Copiez le résultat après `POSTGRES_PASSWORD=`. Notez-le sur papier, rangé en lieu sûr. **Ne le changez plus ensuite** : la base de données garde le mot de passe de sa création.
3. Enregistrez (le reste du fichier peut rester tel quel). AutoStock refuse de démarrer avec un mot de passe faible et dit pourquoi.

### 5. Démarrer
```
docker compose -f docker-compose.prod.yml up -d --build
```
La première fois prend quelques minutes (téléchargements). Ensuite, AutoStock démarre tout seul avec Windows.

### 6. Premier réglage
Sur le PC du magasin, ouvrez **http://localhost:8080**. Entrez le nom du magasin, votre nom, votre email et un mot de passe : vous devenez le propriétaire. Ajoutez votre équipe dans **Équipe**.

### 7. Ouvrir AutoStock depuis les autres ordinateurs et téléphones
1. Sur le PC du magasin : `ipconfig` → notez l'**Adresse IPv4** (par exemple `192.168.1.20`).
2. Ouvrez le port dans le pare-feu Windows (PowerShell **en administrateur**, une seule fois) :
   ```
   New-NetFirewallRule -DisplayName "AutoStock" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private
   ```
   Le réseau du magasin doit être en « Privé » (Paramètres → Réseau et Internet → votre réseau).
3. Les employés et les téléphones ouvrent `http://192.168.1.20:8080`. Rien à changer dans `.env`.
4. Conseillé : faites **réserver cette adresse** au PC dans la box internet (« bail DHCP statique », votre installateur sait le faire). Sinon elle peut changer quand la box redémarre : refaites alors l'étape 1 et donnez la nouvelle adresse. Sur les ordinateurs, le nom du PC (`hostname`, par exemple `http://COMPTOIR-PC:8080`) marche souvent aussi ; sur les téléphones, rarement.

### 8. Sauvegardes
- Chaque jour à **02:00**, et au démarrage si la dernière date de plus de 24 h (PC éteint la nuit), AutoStock fait une sauvegarde dans le dossier **`backups`**, à côté du programme : `autostock-2026-10-29.dump`. Il garde les 14 derniers jours et 1 par mois pendant 12 mois. Une sauvegarde ne compte qu'une fois relue et vérifiée.
- **Paramètres** montre la dernière sauvegarde. Sans sauvegarde depuis 2 jours, le propriétaire voit « À traiter » sur l'Accueil.
- **Une fois par semaine, copiez le dossier `backups` sur une clé USB ou un espace en ligne** (Google Drive, OneDrive…). Une sauvegarde sur le même disque disparaît avec le disque.
- Une sauvegarde tout de suite : `docker compose -f docker-compose.prod.yml exec app python -m app.backups now`

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

**Revenir à l'ancienne version après une mise à jour réussie** : une base mise à jour ne marche plus avec l'ancienne version (elle refuse de démarrer et le dit). Il faut donc **les deux** : remettre l'ancien dossier **et** restaurer la sauvegarde faite avant la mise à jour (étape 9, fichier `autostock-before-update-....dump`). **Tout ce qui a été saisi depuis la mise à jour est perdu.**

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
- Port 8080 déjà pris : `APP_PORT=8090` dans `.env`, puis l'étape 5, et ouvrez `:8090` au lieu de `:8080`.
- « This request did not come from the AutoStock website » : ouvrez AutoStock directement à l'adresse du PC (`http://localhost:8080` ou `http://<adresse IPv4>:8080`), pas à travers un autre site.
- La page dit « AutoStock could not update » ou « This database was updated by a newer AutoStock » : suivez ce qu'elle dit (étape 10).
- Disque plein : Paramètres le dit ; libérez de la place, copiez les vieilles sauvegardes ailleurs.

---

## English

### The Windows app (recommended)

AutoStock installs like a normal program. No Docker, no commands to type, and **everything works without the internet**.

1. **Install.** Double-click `AutoStock-Setup.exe`. If Windows shows "Windows protected your PC", click **More info**, then **Run anyway** (this shows because the program is not signed yet). Click **Next** until the end. No administrator password is needed.
2. **Open.** Double-click the **AutoStock AI** icon on the desktop. AutoStock opens in its own window. The first time, it creates the shop's database (a few seconds), then asks for the shop's name and the owner's account.
3. **The shop's other computers and phones.** On the same Wi-Fi, open the browser and type `http://PC-NAME:8765` (the PC's name is in Windows Settings > System > About). The first time, Windows asks to allow AutoStock on the network: click **Allow** (private networks).
4. **Closing the window does not stop AutoStock**, so the other devices keep using it. It also starts by itself with Windows. To stop it: Start menu > **Stop AutoStock**.
5. **Backups.** One a day, by itself, in `Documents\AutoStock backups` (the last 14 days, and 1 per month for 12 months). Copy that folder to a USB stick now and then.
6. **Restore a backup.** Stop AutoStock, then in PowerShell: `& "$env:LOCALAPPDATA\Programs\AutoStock\AutoStock.exe" --restore autostock-2026-10-29.dump`
7. **Update.** Run the new `AutoStock-Setup.exe`. The shop's data is never touched, and a backup is made before every database change.
8. **Where is the data?** `%LOCALAPPDATA%\AutoStock` (database, settings, logs). Uninstalling never deletes it.
9. **Ask's online assistant (optional).** Open `%LOCALAPPDATA%\AutoStock\settings.env` in Notepad, paste your Groq key after `GROQ_API_KEY=`, save, then Stop AutoStock and open it again.

### With Docker (for developers)

AutoStock runs on **one PC in the shop**. The other computers and phones open it in their browser, on the same network (Wi-Fi or cable). Nothing is sent to the internet, unless you turn on Groq writing in Settings.

Type every command in **PowerShell**, opened in the AutoStock folder (in Explorer: open the folder, click the address bar, type `powershell`, Enter).

### 1. The PC you need
- Windows 10 or 11, 64-bit.
- 8 GB of memory (16 GB for the AI assistant). 20 GB free on the disk.
- It stays on during opening hours. Set sleep to "Never" when plugged in.

### 2. Install Docker Desktop (once)
1. Download Docker Desktop from https://www.docker.com/products/docker-desktop and install it. Keep **WSL 2** ticked. Restart the PC if asked.
2. Open Docker Desktop, accept the terms, wait for "Engine running".
3. In Docker Desktop: **Settings → General → tick "Start Docker Desktop when you sign in"**. AutoStock then comes back by itself after a power cut, as soon as someone signs in to Windows.
4. **8 GB PC only: give Docker 5 GB of memory.** Otherwise Docker takes only half (4 GB), too little for a big shop while the nightly forecasts run. Docker Desktop has no setting for this with WSL 2 (Settings → Resources says Windows manages it): it is set in a file.
   1. In PowerShell: `notepad "$env:USERPROFILE\.wslconfig"` (Notepad offers to create the file: **Yes**).
   2. Type these two lines, then save:
      ```
      [wsl2]
      memory=5GB
      ```
   3. Quit Docker Desktop (icon near the clock → **Quit Docker Desktop**), type `wsl --shutdown` in PowerShell, then open Docker Desktop again.
   4. To check: `docker info --format "{{.MemTotal}}"` shows about 5 billion (5 GB).

   With 16 GB or more, nothing to do.

### 3. Unzip AutoStock
Unzip it into `C:\AutoStock` (for example). This folder is the program. Your data is kept by Docker, separately: the folder can be replaced at every update.

### 4. Create the `.env` file
1. In the AutoStock folder: `copy .env.example .env` then `notepad .env`.
2. Replace `POSTGRES_PASSWORD=change-me` with a strong password (16 characters or more). To make one, type in PowerShell:
   ```
   -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 | % {[char]$_})
   ```
   Paste the result after `POSTGRES_PASSWORD=`. Write it on paper, kept somewhere safe. **Never change it afterwards**: the database keeps the password it was created with.
3. Save (the rest of the file can stay as it is). AutoStock refuses to start with a weak password and says why.

### 5. Start
```
docker compose -f docker-compose.prod.yml up -d --build
```
The first time takes a few minutes (downloads). After that, AutoStock starts by itself with Windows.

### 6. First setup
On the shop PC, open **http://localhost:8080**. Enter the shop name, your name, email and a password: you become the owner. Add your team on **Team**.

### 7. Open AutoStock from the other computers and phones
1. On the shop PC: `ipconfig` → note the **IPv4 Address** (for example `192.168.1.20`).
2. Allow the port in Windows Firewall (PowerShell **as administrator**, once):
   ```
   New-NetFirewallRule -DisplayName "AutoStock" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private
   ```
   The shop network must be "Private" (Settings → Network & internet → your network).
3. Employees and phones open `http://192.168.1.20:8080`. Nothing to change in `.env`.
4. Recommended: have this address **reserved** for the PC in the internet box ("static DHCP lease", your installer knows how). Otherwise it can change when the box restarts: then do step 1 again and share the new address. On computers the PC's name (`hostname`, for example `http://COMPTOIR-PC:8080`) often works too; on phones, rarely.

### 8. Backups
- Every day at **02:00**, and at start if the last one is older than 24 hours (PC off at night), AutoStock saves a backup in the **`backups`** folder next to the program: `autostock-2026-10-29.dump`. It keeps the last 14 days and 1 per month for 12 months. A backup only counts once it has been read back and checked.
- **Settings** shows the last backup. With no backup for 2 days, the owner sees "Needs action" on Today.
- **Once a week, copy the `backups` folder to a USB stick or a cloud drive** (Google Drive, OneDrive…). A backup on the same disk is lost with the disk.
- A backup right now: `docker compose -f docker-compose.prod.yml exec app python -m app.backups now`

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

**Going back to the old version after a successful update**: an updated database no longer works with the old version (it refuses to start and says so). So you need **both**: put the old folder back **and** restore the backup made before the update (step 9, the `autostock-before-update-....dump` file). **Everything entered since the update is lost.**

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
- Port 8080 already used: `APP_PORT=8090` in `.env`, then step 5, and open `:8090` instead of `:8080`.
- "This request did not come from the AutoStock website": open AutoStock directly at the PC's address (`http://localhost:8080` or `http://<IPv4 address>:8080`), not through another site.
- The page says "AutoStock could not update" or "This database was updated by a newer AutoStock": do what it says (step 10).
- Disk full: Settings says so; free some space, copy old backups elsewhere.
