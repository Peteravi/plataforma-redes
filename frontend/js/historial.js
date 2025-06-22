// frontend/js/historial.js

document.addEventListener('DOMContentLoaded', () => {
  // 1. Resumen estadístico
  fetch('/api/stats/summary')
    .then(res => res.json())
    .then(data => {
      // Promedio por escaneo
      new Chart(document.getElementById('chart-avg'), {
        type: 'bar',
        data: {
          labels: ['Promedio por Escaneo'],
          datasets: [{
            label: 'Dispositivos',
            data: [data.avg_por_escaneo]
          }]
        }
      });

      // Distribución por sistema operativo
      new Chart(document.getElementById('chart-tipo'), {
        type: 'pie',
        data: {
          labels: Object.keys(data.dist_os),
          datasets: [{
            data: Object.values(data.dist_os)
          }]
        }
      });

      // Distribución por estado
      new Chart(document.getElementById('chart-confianza'), {
        type: 'doughnut',
        data: {
          labels: Object.keys(data.dist_estado),
          datasets: [{
            data: Object.values(data.dist_estado)
          }]
        }
      });
    });

  // 2. Alertas
  // 2.1 Alertas por día
  fetch('/api/stats/alerts_per_day')
    .then(res => res.json())
    .then(data => {
      new Chart(document.getElementById('chart-alerts-per-day'), {
        type: 'bar',
        data: {
          labels: data.map(d => d.date),
          datasets: [{
            label: 'Alertas',
            data: data.map(d => d.count)
          }]
        },
        options: {
          scales: { y: { beginAtZero: true } }
        }
      });
    });

  // 2.2 Alertas por tipo
  fetch('/api/stats/alerts_by_type')
    .then(res => res.json())
    .then(data => {
      new Chart(document.getElementById('chart-alerts-by-type'), {
        type: 'pie',
        data: {
          labels: data.map(d => d.alert_type),
          datasets: [{ data: data.map(d => d.count) }]
        }
      });
    });

  // 3. Top dispositivos
  fetch('/api/stats/top_devices?limit=5')
    .then(res => res.json())
    .then(data => {
      new Chart(document.getElementById('chart-top-devices'), {
        type: 'bar',
        data: {
          labels: data.map(d => d.name),
          datasets: [{
            label: 'Apariciones',
            data: data.map(d => d.occurrences)
          }]
        },
        options: {
          indexAxis: 'y',
          scales: { x: { beginAtZero: true } }
        }
      });
    });

  // 4. Duración promedio de escaneo por día
  fetch('/api/stats/scan_duration_by_day')
    .then(res => res.json())
    .then(data => {
      new Chart(document.getElementById('chart-scan-duration'), {
        type: 'line',
        data: {
          labels: data.map(d => d.date),
          datasets: [{
            label: 'Duración (s)',
            data: data.map(d => d.avg_duration),
            fill: false
          }]
        },
        options: {
          scales: { y: { beginAtZero: true } }
        }
      });
    });

  // 5. Serie de tiempo de escaneos (diario/mensual)
  const periodSelect = document.getElementById('period-select');
  let tsChart = null;
  function loadTimeSeries(period) {
    fetch(`/api/stats/timeseries?period=${period}`)
      .then(res => res.json())
      .then(data => {
        const labels = data.map(d => d.period);
        const values = data.map(d => d.total);
        if (tsChart) tsChart.destroy();
        tsChart = new Chart(document.getElementById('chart-timeseries'), {
          type: 'line',
          data: {
            labels,
            datasets: [{ label: 'Escaneos', data: values, fill: false }]
          }
        });
      });
  }
  periodSelect.addEventListener('change', () => loadTimeSeries(periodSelect.value));
  loadTimeSeries(periodSelect.value);
});
