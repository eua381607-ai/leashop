# LeaShop

Plateforme e-commerce complète construite avec **Django**, **PostgreSQL** et **Stripe Checkout**.

## Fonctionnalités

- Catalogue produits : catégories (avec sous-catégories), produits, variantes (taille/couleur), images multiples, gestion de stock
- Recherche, filtrage par catégorie, tri (prix, nouveautés), pagination
- Comptes utilisateurs (email comme identifiant), gestion d'adresses multiples
- Panier persistant : fonctionne pour les visiteurs anonymes (session) **et** se fusionne automatiquement au panier utilisateur à la connexion
- Avis clients avec notes (1 à 5 étoiles)
- Tunnel de commande complet : sélection d'adresse → Stripe Checkout → confirmation
- Paiement Stripe sécurisé par webhook (le stock n'est décrémenté qu'après confirmation réelle du paiement, jamais avant)
- Historique de commandes, statuts (en attente, payée, expédiée, livrée, annulée, remboursée)
- Interface d'administration Django complète pour tout gérer (produits, stock, commandes, utilisateurs)
- Prêt pour la production : configuration par variables d'environnement, fichiers de déploiement Railway inclus

## Installation locale

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Ouvrez .env et renseignez au minimum DJANGO_SECRET_KEY et vos clés Stripe de test

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Le site tourne sur http://127.0.0.1:8000, l'administration sur http://127.0.0.1:8000/admin/.

Si vous devez accéder au site en HTTPS localement (ou si votre navigateur force https://127.0.0.1:8000), installez `django-sslserver` puis utilisez :

```bash
python manage.py runsslserver
```

Cela démarre un serveur de développement Django avec SSL local.

Sans `DATABASE_URL` défini, le projet utilise automatiquement SQLite (fichier `db.sqlite3`) — pratique pour développer sans installer Postgres localement.

## Configuration Stripe (paiement)

1. Créez un compte sur https://dashboard.stripe.com et récupérez vos clés de test (`pk_test_...`, `sk_test_...`).
2. Renseignez-les dans `.env` (`STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`).
3. Pour tester le webhook en local, installez la [Stripe CLI](https://stripe.com/docs/stripe-cli) puis :
   ```bash
   stripe listen --forward-to localhost:8000/payments/stripe/webhook/
   ```
   La CLI affiche un secret `whsec_...` à copier dans `STRIPE_WEBHOOK_SECRET`.
4. Stripe Checkout accepte désormais les méthodes de paiement configurées dans la variable `STRIPE_PAYMENT_METHOD_TYPES`.
   Par défaut, seul `card` est activé, mais vous pouvez ajouter `mobile_money` si votre compte Stripe et votre région le supportent.
5. Pour un paiement Mobile Money direct (hors Stripe), configurez également :
   - `MOBILE_MONEY_API_URL`
   - `MOBILE_MONEY_API_KEY`
   - `MOBILE_MONEY_WEBHOOK_SECRET`
   Ces paramètres permettent d’envoyer la demande au fournisseur Mobile Money et de recevoir le callback de validation.
6. Utilisez une carte de test Stripe (ex. `4242 4242 4242 4242`, toute date future, tout CVC) pour simuler un paiement réussi.

## Déploiement sur Railway

1. Créez un nouveau projet Railway, connectez-le à ce dépôt GitHub.
2. Ajoutez un plugin **PostgreSQL** — Railway injecte automatiquement `DATABASE_URL`.
3. Dans les variables d'environnement du service, ajoutez :
   - `DJANGO_SECRET_KEY` (générez-en une nouvelle, différente de celle en local)
   - `DEBUG=False`
   - `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (utilisez vos clés **live** une fois prêt)
   - `SITE_BASE_URL` (l'URL publique Railway, ex. `https://leashop-production.up.railway.app`)
4. Railway détecte `railway.json`/`Procfile` et exécute automatiquement les migrations + `collectstatic` au déploiement.
5. Dans le dashboard Stripe, ajoutez un endpoint webhook pointant vers `https://votre-domaine/payments/stripe/webhook/` pour l'événement `checkout.session.completed`.

## Structure du projet

```
config/       # Réglages Django, urls racine, wsgi/asgi
accounts/     # Utilisateur custom (email), adresses
catalog/      # Catégories, produits, variantes, avis
cart/         # Panier session + utilisateur, fusion à la connexion
orders/       # Commandes, snapshot des articles achetés
payments/     # Intégration Stripe Checkout + webhook
templates/    # Templates globaux (base, navbar, footer)
static/       # CSS/JS
```

## Prochaines étapes possibles

- Emails transactionnels (confirmation de commande, expédition)
- Codes promo / réductions
- Gestion des retours et remboursements depuis l'admin
- API REST (Django REST Framework) si un frontend séparé (mobile, SPA) est envisagé plus tard
# leashop
# leashop
