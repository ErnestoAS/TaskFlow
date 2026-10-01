---
name: django-docs
description: Consulta la documentación oficial y versionada de Django 5.2 LTS (y de Bootstrap 5, django-bootstrap5 o DRF si se agregan) vía llms.txt / markdown antes de escribir o revisar modelos, vistas, formularios, permisos, autenticación o plantillas. Úsala cuando haya dudas sobre una API de Django.
---

# Documentación de Django para TaskFlow

El proyecto está fijado a **Django 5.2 LTS** (ver `pyproject.toml`). No respondas de memoria sobre
APIs que cambian entre versiones: consulta la documentación **de la versión fijada** y cita la
página usada.

## Fuentes (en orden de preferencia)

| Tema | Índice / sitio | Notas |
| --- | --- | --- |
| Django | https://docs.djangoproject.com/llms.txt | Usa páginas de `/en/5.2/`. |
| django-bootstrap5 | https://django-bootstrap5.readthedocs.io/en/latest/ | Cuando se agreguen vistas con formularios. |
| Bootstrap 5 | https://getbootstrap.com/docs/5.3/ | Componentes y utilidades CSS. |
| DRF | https://www.django-rest-framework.org/ | Solo si se agrega una API. |

Procedimiento:

1. Descarga el `llms.txt` correspondiente y localiza la(s) página(s) relevantes.
2. Si existe versión markdown de la página, úsala (más barata y precisa que el HTML).
3. Al reportar al usuario enlaza la versión HTML.

## Páginas clave para este proyecto

- Modelos y campos: https://docs.djangoproject.com/en/5.2/ref/models/fields/
- Restricciones (`CheckConstraint`, `UniqueConstraint`): https://docs.djangoproject.com/en/5.2/ref/models/constraints/
- `ManyToManyField` (asignados): https://docs.djangoproject.com/en/5.2/topics/db/examples/many_to_many/
- Usuario personalizado: https://docs.djangoproject.com/en/5.2/topics/auth/customizing/
- Vistas basadas en clases: https://docs.djangoproject.com/en/5.2/topics/class-based-views/
- Formularios: https://docs.djangoproject.com/en/5.2/topics/forms/
- Mensajes: https://docs.djangoproject.com/en/5.2/ref/contrib/messages/
- Despliegue (checklist): https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
