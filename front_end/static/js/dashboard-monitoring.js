document.addEventListener('DOMContentLoaded', function() {
    const metricsTable = document.getElementById('metrics-table');
    const logsContent = document.getElementById('logs-content');
    const refreshBtn = document.getElementById('refresh-btn');
    
    // Fonction pour charger les métriques
    async function loadMetrics() {
        try {
            const response = await fetch('/metrics');
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            const data = await response.json();
            
            let tableHtml = '';
            for (const [endpoint, metrics] of Object.entries(data)) {
                tableHtml += `
                    <tr>
                        <td>${endpoint}</td>
                        <td>${metrics.count}</td>
                        <td>${metrics.avg_time.toFixed(4)}</td>
                        <td>${metrics.min_time.toFixed(4)}</td>
                        <td>${metrics.max_time.toFixed(4)}</td>
                    </tr>
                `;
            }
            
            if (tableHtml === '') {
                tableHtml = '<tr><td colspan="5" class="text-center">Aucune donnée disponible</td></tr>';
            }
            
            metricsTable.innerHTML = tableHtml;
        } catch (error) {
            console.error('Erreur lors du chargement des métriques:', error);
            metricsTable.innerHTML = `<tr><td colspan="5" class="text-center text-danger">Erreur lors du chargement des métriques: ${error.message}</td></tr>`;
        }
    }
    
    // Fonction pour charger les logs
    async function loadLogs() {
        try {
            console.log("Chargement des logs...");
            logsContent.textContent = "Chargement des logs...";
            
            const response = await fetch('/logs');
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const data = await response.json();
            console.log("Logs récupérés:", data);
            
            if (data.logs && Array.isArray(data.logs) && data.logs.length > 0) {
                logsContent.textContent = data.logs.join('');
                // Défiler automatiquement vers le bas pour voir les logs les plus récents
                logsContent.scrollTop = logsContent.scrollHeight;
            } else {
                logsContent.textContent = "Aucun log disponible";
            }
        } catch (error) {
            console.error('Erreur lors du chargement des logs:', error);
            logsContent.textContent = `Erreur lors du chargement des logs: ${error.message}`;
        }
    }
    
    // Charger les données au chargement de la page
    loadMetrics();
    loadLogs();
    
    // Actualiser les données quand le bouton est cliqué
    refreshBtn.addEventListener('click', function() {
        loadMetrics();
        loadLogs();
    });
    
    // Actualiser automatiquement toutes les 30 secondes
    setInterval(function() {
        loadMetrics();
        loadLogs();
    }, 30000);
});