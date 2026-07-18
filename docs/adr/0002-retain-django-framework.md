# 0002-retain-django-framework

We decided to leverage the existing Python 3.13 + Django 5.1.2 + Celery codebase instead of rewriting the application in Node.js/TypeScript (as originally described in the specification index). Because the current backend already has working models, search integration, task runners, and API structures, retaining the Django framework avoids redundant development and ensures the project moves quickly to the payment and escrow implementation phase.
