document.addEventListener('DOMContentLoaded', () => {
  // Inicializamos Socket.IO
  const socket = io();

  // Referencias a elementos del DOM
  const scanButton = document.getElementById('scan-button');
  const statsButton = document.getElementById('stats-button');
  const clustersButton = document.getElementById('clusters-button');
  const alertasButton = document.getElementById('alertas-button');
  const resultsDiv = document.getElementById('scan-results');
  const loadingSpinner = document.getElementById('loading-spinner');
  const statsModal = new bootstrap.Modal(document.getElementById('statsModal'));
  const clustersModal = new bootstrap.Modal(document.getElementById('clustersModal'));
  const alertasModal = new bootstrap.Modal(document.getElementById('alertasModal'));
  const alertasBadge = document.getElementById('alertas-badge');

  // ESCANEO MANUAL
  scanButton.addEventListener('click', async () => {
    loadingSpinner.classList.remove('d-none');
    resultsDiv.classList.add('d-none');
    try {
      const res = await fetch('/api/escaneo');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if (data.status === 'error') {
        showError(data.message);
      } else {
        renderDeviceTable(data.dispositivos);
        updateResultsSummary(data);
      }
    } catch (err) {
      console.error(err);
      showError('Error al realizar el escaneo.');
    } finally {
      loadingSpinner.classList.add('d-none');
      resultsDiv.classList.remove('d-none');
    }
  });

  // ESTADÍSTICAS
  statsButton.addEventListener('click', handleStats);

  // ALERTAS
  alertasButton?.addEventListener('click', showAlertasModal);
  checkAlertas();
  setInterval(checkAlertas, 30000);

  // FILTROS
  ['filter-trust', 'filter-type'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', updateDeviceTable);
  });
  document.getElementById('filter-search')?.addEventListener('input', updateDeviceTable);
  document.getElementById('filter-clear')?.addEventListener('click', () => {
    ['filter-search', 'filter-trust', 'filter-type'].forEach(i => document.getElementById(i).value = '');
    updateDeviceTable();
  });

  // ESCANEOS AUTOMÁTICOS en tiempo real
  socket.on('scan_complete', data => {
    renderDeviceTable(data.dispositivos);
    updateResultsSummary(data);
    showToast('Escaneo completado automáticamente', 'info');
  });

  // Render inicial
  updateDeviceTable();

  // =========================== FUNCIONES ===========================

  async function updateDeviceTable() {
    const trust = document.getElementById('filter-trust').value;
    const tipo = document.getElementById('filter-type').value;
    const busq = document.getElementById('filter-search').value;
    let url = '/api/dispositivos?';
    if (trust) url += `confiable=${trust}&`;
    if (tipo) url += `tipo=${tipo}&`;
    if (busq) url += `busqueda=${encodeURIComponent(busq)}`;
    try {
      const res = await fetch(url);
      const d = await res.json();
      if (d.status === 'success') renderDeviceTable(d.dispositivos);
    } catch (err) {
      console.error('Error filtros:', err);
    }
  }

  function renderDeviceTable(dispositivos) {
    const tbody = document.getElementById('tabla-dispositivos');
    tbody.innerHTML = dispositivos.map(d => {
      const ip = maskIp(d.ip);
      const mac = d.mac;
      const nombre = d.nombre_dispositivo;
      const tipoD = d.tipo_dispositivo || 'Desconocido';
      const fecha = new Date(d.ultima_detectado).toLocaleString();
      const notas = (d.notas || '').substring(0, 20) + ((d.notas || '').length > 20 ? '...' : '');
      const confi = d.es_confiable ? 'Confiado' : 'No confiado';
      const icons = { PC: 'bi-pc', Mac: 'bi-apple', Móvil: 'bi-phone', Desconocido: 'bi-question-circle' };
      const icon = icons[tipoD] || icons.Desconocido;
      const clase = d.es_confiable ? 'text-success' : 'text-danger';
      return `
        <tr data-mac="${mac}">
          <td>${ip}</td>
          <td>${mac}</td>
          <td>${nombre}</td>
          <td><i class="bi ${icon} me-1"></i>${tipoD}</td>
          <td><span class="${clase}">${confi}</span></td>
          <td>${fecha}</td>
          <td>${notas}</td>
          <td><button class="btn btn-sm btn-outline-primary manage-device">
                <i class="bi bi-gear"></i>
              </button></td>
        </tr>`;
    }).join('');

    // Asociar gestión dispositivo
    tbody.querySelectorAll('.manage-device').forEach(btn => {
      btn.addEventListener('click', () => {
        const mac = btn.closest('tr').dataset.mac;
        const device = dispositivos.find(x => x.mac === mac);
        showDeviceModal(device);
      });
    });
  }

  function showDeviceModal(d) {
    const modal = new bootstrap.Modal(document.getElementById('deviceModal'));
    document.querySelector('#deviceModal .modal-title')
      .textContent = `Gestionar ${d.nombre_dispositivo}`;
    document.getElementById('trust-status').value = d.es_confiable;
    document.getElementById('device-notes').value = d.notas || '';
    document.getElementById('save-device-btn').onclick = async () => {
      try {
        await fetch('/api/dispositivos/marcar-confiable', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mac: d.mac, es_confiable: document.getElementById('trust-status').value })
        });
        await fetch('/api/dispositivos/agregar-nota', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mac: d.mac, nota: document.getElementById('device-notes').value })
        });
        showToast('Cambios guardados', 'success');
        updateDeviceTable();
        modal.hide();
      } catch (e) {
        console.error(e);
        showToast('Error al guardar', 'danger');
      }
    };
    modal.show();
  }

  async function handleStats() {
    const c = document.getElementById('stats-content');
    c.innerHTML = `<div class="text-center my-4">
                     <div class="spinner-border text-primary" role="status"></div>
                   </div>`;
    statsModal.show();
    try {
      const res = await fetch('/api/estadisticas');
      const d = await res.json();
      if (d.status !== 'success') throw new Error(d.message);
      c.innerHTML = renderStats(d);
      document.getElementById('export-pdf-btn')
        .addEventListener('click', exportStatsPDF);
    } catch (e) {
      c.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
    }
  }

  // clusters
  clustersButton.addEventListener('click', async () => {
    // Contenedor del canvas
    const container = document.querySelector('#chart-clusters').parentElement;
    // Spinner mientras carga
    container.innerHTML = `
      <div class="text-center my-4">
        <div class="spinner-border text-primary" role="status"></div>
      </div>`;
    try {
      const res = await fetch('/api/stats/clusters');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json(); // [{dispositivo_id, mac, cluster}, ...]

      // Calcular conteos
      const counts = data.reduce((acc, { cluster }) => {
        acc[cluster] = (acc[cluster] || 0) + 1;
        return acc;
      }, {});
      const labels = Object.keys(counts).map(c => `Cluster ${c}`);
      const values = Object.values(counts);
      const total = values.reduce((sum, v) => sum + v, 0);

      // Renderizar canvas
      container.innerHTML = '<canvas id="chart-clusters" height="250"></canvas>';
      const ctx = document.getElementById('chart-clusters');

      new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels,
          datasets: [{
            data: values,
            backgroundColor: labels.map((_, i) => `hsl(${i * 360 / labels.length}, 70%, 60%)`),
            borderColor: '#ffffff',
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom',
              labels: { boxWidth: 12 }
            },
            tooltip: {
              callbacks: {
                label: context => {
                  const count = context.raw;
                  const percent = ((count / total) * 100).toFixed(1);
                  return `${context.label}: ${count} (${percent}%)`;
                }
              }
            }
          }
        }
      });
    } catch (err) {
      container.innerHTML = `<div class="alert alert-danger">Error cargando clusters: ${err.message}</div>`;
    }
    clustersModal.show();
  });


  function renderStats(d) {
    return `
    <div class="row">
      <div class="col-12 text-end mb-3">
        <button id="export-pdf-btn" class="btn btn-danger">
          <i class="bi bi-file-earmark-pdf"></i> Exportar PDF
        </button>
      </div>
      <div class="col-md-6">
        <div class="card h-100">
          <div class="card-header bg-primary text-white">Resumen</div>
          <div class="card-body">
            <div class="d-flex justify-content-between">
              Total: <strong>${d.total_dispositivos?.[0]?.total || 0}</strong>
            </div>
            <ul class="list-group mt-3">
              ${d.dispositivos_por_estado.map(i =>
      `<li class="list-group-item d-flex justify-content-between">
                  ${i.estado}
                  <span class="badge bg-primary">${i.cantidad}</span>
                </li>`).join('')}
            </ul>
          </div>
        </div>
      </div>
      <div class="col-md-6">
        <div class="card h-100">
          <div class="card-header bg-primary text-white">Últimos escaneos</div>
          <div class="card-body">
            <ul class="list-group">
              ${d.ultimos_escaneos.map(e =>
        `<li class="list-group-item">
                   ${new Date(e.fecha).toLocaleString()} —
                   ${e.total_dispositivos} disp. (${e.duracion_segundos}s)
                 </li>`).join('')}
            </ul>
          </div>
        </div>
      </div>
    </div>`;
  }

  async function exportStatsPDF() {
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF('p', 'pt', 'a4');
    const elem = document.getElementById('stats-content');
    const canvas = await html2canvas(elem);
    const img = canvas.toDataURL('image/png');
    const width = pdf.internal.pageSize.getWidth();
    const height = canvas.height * width / canvas.width;
    pdf.addImage(img, 'PNG', 0, 0, width, height);
    pdf.save('estadisticas.pdf');
  }

  // ALERTAS

  async function showAlertasModal() {
    const c = document.getElementById('alertas-content');
    c.innerHTML = `<div class="text-center my-4">
                     <div class="spinner-border text-primary" role="status"></div>
                   </div>`;
    try {
      const res = await fetch('/api/alertas');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const alertas = await res.json();
      c.innerHTML = renderAlertas(alertas);
      if (alertas.length === 0) alertasBadge.classList.add('d-none');
    } catch (err) {
      c.innerHTML = `<div class="alert alert-danger">Error cargando alertas: ${err.message}</div>`;
    }
    alertasModal.show();
  }

  async function checkAlertas() {
    try {
      const res = await fetch('/api/alertas');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const alertas = await res.json();
      if (alertas.length > 0) {
        alertasBadge.textContent = alertas.length;
        alertasBadge.classList.remove('d-none');
      } else {
        alertasBadge.classList.add('d-none');
      }
    } catch (err) {
      console.error('Error verificando alertas:', err);
    }
  }

  function renderAlertas(alertas) {
    if (!alertas.length) {
      return `<div class="alert alert-info">No hay alertas pendientes</div>`;
    }
    return `
      <div class="list-group">
        ${alertas.map(a => `
          <div class="list-group-item ${a.leida
        ? 'bg-light'
        : 'bg-primary bg-opacity-10 border-start border-primary border-3'}">
            <div class="d-flex justify-content-between align-items-center">
              <h6 class="mb-0 text-primary">
                <i class="bi bi-exclamation-circle-fill me-2"></i>${a.tipo}
              </h6>
              <small class="text-muted">
                ${new Date(a.fecha).toLocaleString()}
              </small>
            </div>
            <p class="mt-2 mb-1">${a.mensaje}</p>
            <small class="text-muted d-block">
              MAC: ${a.mac} | IP: ${a.ip}
            </small>
          </div>`).join('')}
      </div>`;
  }

  // UTILIDADES

  function updateResultsSummary(d) {
    resultsDiv.className = 'alert alert-info';
    resultsDiv.innerHTML = `
      <i class="bi bi-check-circle-fill text-success me-2"></i>
      <strong>Escaneo completado:</strong>
      ${d.total} dispositivos en ${d.duracion_segundos}s.
    `;
  }

  function showError(msg) {
    resultsDiv.className = 'alert alert-danger';
    resultsDiv.innerHTML = `<i class="bi bi-exclamation-triangle me-2"></i>${msg}`;
    resultsDiv.classList.remove('d-none');
  }

  function maskIp(ip) {
    const p = ip.split('.');
    return p.length === 4 ? `${p[0]}.${p[1]}.${p[2]}.xxx` : ip;
  }

  function showToast(msg, type = 'success') {
    const container = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = `toast show bg-${type} text-white`;
    t.innerHTML = `<div class="toast-body">${msg}</div>`;
    container.appendChild(t);
    setTimeout(() => { t.remove(); }, 3000);
  }
});
