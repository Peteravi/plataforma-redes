document.addEventListener('DOMContentLoaded', () => {
  const periodSelect = document.getElementById('period-select');
  let tsChart = null;

  loadSummary();
  loadAlertsPerDay();
  loadAlertsByType();
  loadTopDevices();
  loadScanDuration();
  loadTimeSeries(periodSelect.value);
  periodSelect.addEventListener('change', () => loadTimeSeries(periodSelect.value));

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
          datasets: [{ label: 'Dispositivos', data: [data.avg_por_escaneo || 0] }],
        },
      });

      new Chart(document.getElementById('chart-tipo'), {
        type: 'pie',
        data: {
          labels: Object.keys(data.dist_tipo || {}),
          datasets: [{ data: Object.values(data.dist_tipo || {}) }],
        },
      });

      new Chart(document.getElementById('chart-confianza'), {
        type: 'doughnut',
        data: {
          labels: Object.keys(data.dist_confianza || {}),
          datasets: [{ data: Object.values(data.dist_confianza || {}) }],
        },
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
          labels: data.map((item) => item.date),
          datasets: [{ label: 'Alertas', data: data.map((item) => item.count) }],
        },
        options: { scales: { y: { beginAtZero: true } } },
      });
    } catch (error) {
      console.error('Error cargando alerts_per_day:', error);
    }
  }

  async function loadAlertsByType() {
    try {
      const data = await fetchJson('/api/stats/alerts_by_type');
      new Chart(document.getElementById('chart-alerts-by-type'), {
        type: 'pie',
        data: {
          labels: data.map((item) => item.alert_type),
          datasets: [{ data: data.map((item) => item.count) }],
        },
      });
    } catch (error) {
      console.error('Error cargando alerts_by_type:', error);
    }
  }

  async function loadTopDevices() {
    try {
      const data = await fetchJson('/api/stats/top_devices?limit=5');
      new Chart(document.getElementById('chart-top-devices'), {
        type: 'bar',
        data: {
          labels: data.map((item) => item.name),
          datasets: [{ label: 'Apariciones', data: data.map((item) => item.occurrences) }],
        },
        options: {
          indexAxis: 'y',
          scales: { x: { beginAtZero: true } },
        },
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
          labels: data.map((item) => item.date),
          datasets: [{ label: 'Duración (s)', data: data.map((item) => item.avg_duration), fill: false }],
        },
        options: { scales: { y: { beginAtZero: true } } },
      });
    } catch (error) {
      console.error('Error cargando scan_duration_by_day:', error);
    }
  }

  async function loadTimeSeries(period) {
    try {
      const data = await fetchJson(`/api/stats/timeseries?period=${period}`);
      const labels = data.map((item) => item.period);
      const values = data.map((item) => item.total);
      if (tsChart) tsChart.destroy();
      tsChart = new Chart(document.getElementById('chart-timeseries'), {
        type: 'line',
        data: { labels, datasets: [{ label: 'Escaneos', data: values, fill: false }] },
      });
    } catch (error) {
      console.error('Error cargando timeseries:', error);
    }
  }
});