import time
import logging
import functools
import traceback
from contextvars import ContextVar
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
import json
import os

# Configuration du logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("application.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# Créer un logger spécifique pour le monitoring
logger = logging.getLogger("monitoring")
logger.setLevel(logging.INFO)

# S'assurer que le fichier de log existe
if not os.path.exists("application.log"):
    with open("application.log", "w", encoding="utf-8") as f:
        f.write("Initialisation du fichier de log\n")
    logger.info("Fichier de log créé")

# Variable de contexte pour suivre les requêtes
request_id_var = ContextVar("request_id", default=None)
current_span_var = ContextVar("current_span", default=None)

class PerformanceMonitor:
    """Utilitaire pour suivre les performances des fonctions et méthodes"""
    
    _metrics = {}
    
    @classmethod
    def time_function(cls, func):
        """Décorateur pour mesurer le temps d'exécution d'une fonction"""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            function_name = f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            request_id = request_id_var.get()
            parent_span = current_span_var.get()
            
            # Créer un nouveau span (segment de trace)
            span_id = str(uuid.uuid4())
            current_span_var.set(span_id)
            
            logger = logging.getLogger(function_name)
            logger.info(f"[{request_id}][{span_id}] DÉBUT: parent={parent_span}")
            
            try:
                # Exécuter la fonction
                result = await func(*args, **kwargs)
                
                # Mesurer le temps d'exécution
                execution_time = time.time() - start_time
                
                # Stocker les métriques
                if function_name not in cls._metrics:
                    cls._metrics[function_name] = {
                        "count": 0,
                        "total_time": 0,
                        "min_time": float("inf"),
                        "max_time": 0
                    }
                
                cls._metrics[function_name]["count"] += 1
                cls._metrics[function_name]["total_time"] += execution_time
                cls._metrics[function_name]["min_time"] = min(cls._metrics[function_name]["min_time"], execution_time)
                cls._metrics[function_name]["max_time"] = max(cls._metrics[function_name]["max_time"], execution_time)
                
                # Journaliser la fin de l'exécution
                logger.info(f"[{request_id}][{span_id}] FIN: durée={execution_time:.4f}s - succès")
                
                return result
            except Exception as e:
                # En cas d'erreur, journaliser l'exception
                execution_time = time.time() - start_time
                logger.error(f"[{request_id}][{span_id}] ERREUR: durée={execution_time:.4f}s - {str(e)}")
                logger.error(f"[{request_id}][{span_id}] TRACE: {traceback.format_exc()}")
                raise
            finally:
                # Restaurer le span parent
                current_span_var.set(parent_span)
        
        return wrapper
    
    @classmethod
    def record_endpoint_metrics(cls, path, method, execution_time):
        """Enregistrer les métriques pour un endpoint"""
        endpoint_key = f"{method} {path}"
        
        if endpoint_key not in cls._metrics:
            cls._metrics[endpoint_key] = {
                "count": 0,
                "total_time": 0,
                "min_time": float("inf"),
                "max_time": 0
            }
        
        cls._metrics[endpoint_key]["count"] += 1
        cls._metrics[endpoint_key]["total_time"] += execution_time
        cls._metrics[endpoint_key]["min_time"] = min(cls._metrics[endpoint_key]["min_time"], execution_time)
        cls._metrics[endpoint_key]["max_time"] = max(cls._metrics[endpoint_key]["max_time"], execution_time)
    
    @classmethod
    def get_metrics(cls):
        """Récupérer les métriques collectées"""
        result = {}
        for endpoint_name, metrics in cls._metrics.items():
            result[endpoint_name] = {
                "count": metrics["count"],
                "avg_time": metrics["total_time"] / metrics["count"] if metrics["count"] > 0 else 0,
                "min_time": metrics["min_time"] if metrics["min_time"] != float("inf") else 0,
                "max_time": metrics["max_time"]
            }
        return result
    
    @classmethod
    def reset_metrics(cls):
        """Réinitialiser les métriques"""
        cls._metrics = {}

class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware pour surveiller les requêtes HTTP"""
    
    async def dispatch(self, request: Request, call_next):
        # Générer un ID unique pour la requête
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)
        current_span_var.set(None)
        
        # Récupérer les informations de la requête
        path = request.url.path
        method = request.method
        
        # Journaliser le début de la requête
        start_time = time.time()
        logger.info(f"[{request_id}] REQUÊTE DÉBUT: {method} {path}")
        
        # Récupérer les paramètres de la requête
        query_params = dict(request.query_params)
        headers = dict(request.headers)
        sensitive_headers = ["authorization", "cookie"]
        for header in sensitive_headers:
            if header in headers:
                headers[header] = "***MASQUÉ***"
        
        body = None
        if method in ["POST", "PUT", "PATCH"]:
            try:
                # Essayer de lire le corps de la requête
                body_bytes = await request.body()
                request._body = body_bytes  # Restaurer le corps pour les handlers suivants
                
                content_type = request.headers.get("content-type", "")
                if "application/json" in content_type:
                    body = json.loads(body_bytes)
                elif "application/x-www-form-urlencoded" in content_type:
                    form = await request.form()
                    body = dict(form)
                    # Masquer les mots de passe
                    if "password" in body:
                        body["password"] = "***MASQUÉ***"
            except Exception as e:
                logger.warning(f"[{request_id}] Impossible de lire le corps de la requête: {str(e)}")
        
        request_details = {
            "method": method,
            "path": path,
            "query_params": query_params,
            "headers": headers,
            "body": body
        }
        
        logger.info(f"[{request_id}] DÉTAILS REQUÊTE: {json.dumps(request_details, indent=2, default=str)}")
        
        try:
            # Exécuter le handler de la requête
            response = await call_next(request)
            
            # Mesurer le temps d'exécution
            execution_time = time.time() - start_time
            
            # Enregistrer les métriques pour cet endpoint
            PerformanceMonitor.record_endpoint_metrics(path, method, execution_time)
            
            # Journaliser la fin de la requête
            logger.info(f"[{request_id}] REQUÊTE FIN: {method} {path} - statut={response.status_code}, durée={execution_time:.4f}s")
            
            # Ajouter des en-têtes de performance à la réponse
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{execution_time:.4f}s"
            
            return response
        except Exception as e:
            # En cas d'erreur, journaliser l'exception
            execution_time = time.time() - start_time
            logger.error(f"[{request_id}] REQUÊTE ERREUR: {method} {path} - {str(e)}, durée={execution_time:.4f}s")
            logger.error(f"[{request_id}] TRACE: {traceback.format_exc()}")
            
            # Enregistrer les métriques même en cas d'erreur
            PerformanceMonitor.record_endpoint_metrics(path, method, execution_time)
            
            # Créer une réponse d'erreur
            return Response(
                content=json.dumps({
                    "error": str(e),
                    "request_id": request_id
                }),
                status_code=500,
                media_type="application/json",
                headers={"X-Request-ID": request_id, "X-Response-Time": f"{execution_time:.4f}s"}
            )

# Endpoint pour afficher les métriques
async def get_metrics():
    """Endpoint pour récupérer les métriques de performance"""
    return PerformanceMonitor.get_metrics()