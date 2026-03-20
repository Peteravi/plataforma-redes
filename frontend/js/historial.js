// historial.js - Versión final compacta
document.addEventListener('DOMContentLoaded', () => {
  const periodSelect = document.getElementById('period-select');
  let tsChart = null;

  const chartColors = {
    primary: '#0d6efd',
    secondary: '#6c757d',
    success: '#198754',
    warning: '#ffc107',
    danger: '#dc3545',
    info: '#0dcaf0',
    light: '#f8f9fa',
    dark: '#212529',
    palette: ['#0d6efd', '#6c757d', '#198754', '#ffc107', '#dc3545', '#0dcaf0', '#6610f2']
  };

  const baseOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          font: { size: 9, family: "'Open Sans', sans-serif" },
          usePointStyle: true,
          boxWidth: 8
        }
      },
      tooltip: {
        backgroundColor: 'rgba(0,0,0,0.8)',
        titleColor: '#fff',
        bodyColor: '#f8f9fa',
        borderColor: '#0d6efd',
        borderWidth: 1,
        cornerRadius: 6,
        displayColors: true,
        callbacks: {
          label: (context) => {
            let label = context.dataset.label || '';
            if (label) label += ': ';
            if (context.parsed.y !== undefined) {
              label += context.parsed.y;
            } else if (context.parsed !== undefined) {
              label += context.parsed;
            }
            return label;
          }
        }
      }
    },
    animation: {
      duration: 600,
      easing: 'easeOutQuart'
    }
  };

  async function fetchJson(url) {
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || `Error en ${url}`);
    return data;
  }

  async function loadSummary() {
    try {
      const data = await fetchJson('/api/stats/summary');

      new Chart(document.getElementById('chart-avg'), {
        type: 'bar',
        data: {
          labels: ['Promedio por escaneo'],
          datasets: [{
            label: 'Dispositivos',
            data: [data.avg_por_escaneo || 0],
            backgroundColor: chartColors.primary,
            borderRadius: 4
          }]
        },
        options: {
          ...baseOptions,
          scales: { y: { beginAtZero: true, title: { display: true, text: 'Dispositivos', font: { size: 9 } } } }
        }
      });

      new Chart(document.getElementById('chart-tipo'), {
        type: 'pie',
        data: {
          labels: Object.keys(data.dist_tipo || {}),
          datasets: [{
            data: Object.values(data.dist_tipo || {}),
            backgroundColor: chartColors.palette,
            borderWidth: 0
          }]
        },
        options: baseOptions
      });

      new Chart(document.getElementById('chart-confianza'), {
        type: 'doughnut',
        data: {
          labels: Object.keys(data.dist_confianza || {}),
          datasets: [{
            data: Object.values(data.dist_confianza || {}),
            backgroundColor: [chartColors.success, chartColors.danger],
            borderWidth: 0
          }]
        },
        options: baseOptions
      });
    } catch (error) {
      console.error('Error cargando summary:', error);
    }
  }

  async function loadAlertsPerDay() {
    try {
      const data = await fetchJson('/api/stats/alerts_per_day');
      new Chart(document.getElementById('chart-alerts-per-day'), {
        type: 'bar',
        data: {
          labels: data.map(item => item.date),
          datasets: [{
            label: 'Alertas',
            data: data.map(item => item.count),
            backgroundColor: chartColors.warning,
            borderRadius: 4
          }]
        },
        options: {
          ...baseOptions,
          scales: { y: { beginAtZero: true, title: { display: true, text: 'Número de alertas', font: { size: 9 } } } }
        }
      });
    } catch (error) {
      console.error('Error cargando alerts_per_day:', error);
    }
  }

  async function loadTopDevices() {
    try {
      const data = await fetchJson('/api/stats/top_devices?limit=5');
      new Chart(document.getElementById('chart-top-devices'), {
        type: 'bar',
        data: {
          labels: data.map(item => item.name),
          datasets: [{
            label: 'Apariciones',
            data: data.map(item => item.occurrences),
            backgroundColor: chartColors.info,
            borderRadius: 4
          }]
        },
        options: {
          ...baseOptions,
          indexAxis: 'y',
          scales: {
            x: { beginAtZero: true, title: { display: true, text: 'Frecuencia', font: { size: 9 } } },
            y: { title: { display: true, text: 'Dispositivo', font: { size: 9 } } }
          }
        }
      });
    } catch (error) {
      console.error('Error cargando top_devices:', error);
    }
  }

  async function loadScanDuration() {
    try {
      const data = await fetchJson('/api/stats/scan_duration_by_day');
      new Chart(document.getElementById('chart-scan-duration'), {
        type: 'line',
        data: {
          labels: data.map(item => item.date),
          datasets: [{
            label: 'Duración (segundos)',
            data: data.map(item => item.avg_duration),
            borderColor: chartColors.primary,
            backgroundColor: 'rgba(13, 110, 253, 0.05)',
            fill: true,
            tension: 0.3,
            pointBackgroundColor: chartColors.primary,
            pointBorderColor: '#fff',
            pointRadius: 2,
            pointHoverRadius: 4
          }]
        },
        options: {
          ...baseOptions,
          scales: { y: { beginAtZero: true, title: { display: true, text: 'Segundos', font: { size: 9 } } } }
        }
      });
    } catch (error) {
      console.error('Error cargando scan_duration_by_day:', error);
    }
  }

  async function loadTimeSeries(period) {
    try {
      const data = await fetchJson(`/api/stats/timeseries?period=${period}`);
      const labels = data.map(item => item.period);
      const values = data.map(item => item.total);
      if (tsChart) tsChart.destroy();
      tsChart = new Chart(document.getElementById('chart-timeseries'), {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: 'Escaneos realizados',
            data: values,
            borderColor: chartColors.success,
            backgroundColor: 'rgba(25, 135, 84, 0.05)',
            fill: true,
            tension: 0.3,
            pointBackgroundColor: chartColors.success,
            pointBorderColor: '#fff',
            pointRadius: 2,
            pointHoverRadius: 4
          }]
        },
        options: {
          ...baseOptions,
          scales: { y: { beginAtZero: true, title: { display: true, text: 'Cantidad de escaneos', font: { size: 9 } } } }
        }
      });
    } catch (error) {
      console.error('Error cargando timeseries:', error);
    }
  }

  // Cargar solo los gráficos esenciales
  loadSummary();
  loadAlertsPerDay();
  loadTopDevices();
  loadScanDuration();
  loadTimeSeries(periodSelect.value);
  periodSelect.addEventListener('change', () => loadTimeSeries(periodSelect.value));
});