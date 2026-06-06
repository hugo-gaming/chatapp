# 💬 ChatApp — Style Discord

Application de messagerie en temps réel avec WebSockets.

## 📁 Fichiers

```
chat-app/
├── server.py   ← Le serveur Python (WebSocket + base de données)
├── index.html  ← L'interface (ouvre dans le navigateur)
└── README.md
```

## 🚀 Installation et lancement

### 1. Installe la dépendance Python
Ouvre un terminal et tape :
```bash
pip install websockets
```

### 2. Lance le serveur
```bash
python server.py
```
Tu devrais voir :
```
✅ Base de données initialisée.
🚀 Serveur démarré sur ws://localhost:8765
```

### 3. Ouvre l'appli
Double-clique sur `index.html` pour l'ouvrir dans ton navigateur.

### 4. Crée un compte et discute !
- Clique sur **Inscription** pour créer un compte
- Envoie des messages dans les canaux
- Survole un message pour le **supprimer** ou ajouter une **réaction**
- Ouvre plusieurs onglets avec des comptes différents pour tester le chat en temps réel !

## ✨ Fonctionnalités
- ✅ Inscription / Connexion
- ✅ Canaux : général, gaming, musique
- ✅ Messages en temps réel (WebSocket)
- ✅ Supprimer ses messages
- ✅ Réactions emoji
- ✅ Indicateur "en train d'écrire..."
- ✅ Historique des messages (SQLite)
- ✅ Plusieurs utilisateurs simultanés

## 🌐 Pour que tes potes se connectent
Pour l'instant le serveur est en **local** (juste ton PC).
Pour jouer avec tes potes, il faudra héberger le serveur en ligne
(sur un VPS, Railway, Render, etc.) — dis-le moi et je t'aide !
