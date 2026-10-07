# Logic Team - Entorno local

Django + PostgreSQL en Docker Compose, con frontend HTML/CSS/JS servido por Django en desarrollo.

## Requisitos
- Docker Desktop (con Docker Compose)
- Git

## Primer arranque
1. `cp .env.example .env` (o `make setup`)
2. `docker compose up --build` (o `make up`)
3. Abre http://localhost:8000 (debe decir "Servidor: ok · Base de datos: ok")
4. En otra terminal: `docker compose exec web python manage.py createsuperuser` (o `make superuser`)
5. Django Admin: http://localhost:8000/admin/

## Comandos utiles (Makefile)
| Comando | Que hace |
| --- | --- |
| `make up` / `make down` | Levanta / detiene los contenedores |
| `make test` | Ejecuta pytest |
| `make lint` / `make format` | Ruff |
| `make makemigrations` / `make migrate` | Migraciones |
| `make psql` | Consola de PostgreSQL |
| `make reset-db` | Borra los contenedores y el volumen de la base de datos |

## Estructura
- `config/`: configuracion del proyecto Django
- `game/`: app principal (modelos, API JSON, admin)
- `frontend/`: HTML, CSS y JS Vanilla
