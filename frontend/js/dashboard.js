document.addEventListener('DOMContentLoaded', () => {
  const tablaBody = document.querySelector('#tabla-dispositivos tbody');
  const btnRefresh = document.getElementById('btn-refresh');
  const btnAlertas = document.getElementById('btn-alertas');
  const badgeAlertas = document.getElementById('badge-alertas');
  const searchInput = document.getElementById('search-input');
  const filterTipo = document.getElementById('filter-tipo');
  const filterConfiable = document.getElementById('filter-confiable');
  const notaModalEl = document.getElementById('notaModal');
  const notaModal = new bootstrap.Modal(notaModalEl);
  const alertasModal = new bootstrap.Modal(document.getElementById('alertasModal'));

  let dispositivos = [];

  init();

  function init() {
    cargarTodo();
    btnRefresh.addEventListener('click', ejecutarEscaneoManual);
    btnAlertas.addEventListener('click', mostrarAlertas);
    searchInput.addEventListener('input', renderTabla);
    filterTipo.addEventListener('change', renderTabla);
    filterConfiable.addEventListener('change', renderTabla);
    document.getElementById('guardar-nota').addEventListener('click', guardarNota);
  }

  async function cargarTodo() {
    await Promise.all([
      cargarDispositivos(),
      cargarAlertas(),
      cargarEstadisticas(),
    ]);
  }

  async function fetchJson(url, options = {}) {
    const res = await fetch(url, options);
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.message || 'Error en la solicitud');
    }
    return data;
  }

  async function ejecutarEscaneoManual() {
    const original = btnRefresh.innerHTML;
    btnRefresh.disabled = true;
    btnRefresh.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Escaneando...';

    try {
      const data = await fetchJson('/api/escaneo');
      if (data.status !== 'success' && data.status !== 'partial_success') {
        throw new Error(data.message || 'No se pudo completar el escaneo');
      }

      await cargarTodo();
      mostrarToast('Escaneo completado correctamente', 'success');
    } catch (error) {
      console.error(error);
      mostrarToast(error.message || 'Error al escanear', 'danger');
    } finally {
      btnRefresh.disabled = false;
      btnRefresh.innerHTML = original;
    }
  }

  async function cargarDispositivos() {
    try {
      const data = await fetchJson('/api/dispositivos');
      dispositivos = Array.isArray(data.dispositivos) ? data.dispositivos : [];
      poblarFiltroTipos(dispositivos);
      renderTabla();
    } catch (error) {
      console.error('Error cargando dispositivos:', error);
      tablaBody.innerHTML = `
        <tr>
          <td colspan="8" class="text-center text-danger py-4">No se pudieron cargar los dispositivos</td>
        </tr>
      `;
    }
  }

  function poblarFiltroTipos(items) {
    const tipoActual = filterTipo.value;
    const tipos = [...new Set(items.map((d) => d.tipo_dispositivo || 'Desconocido'))].sort();

    filterTipo.innerHTML = '<option value="">Todos los tipos</option>';
    tipos.forEach((tipo) => {
      const option = document.createElement('option');
      option.value = tipo;
      option.textContent = tipo;
      filterTipo.appendChild(option);
    });

    filterTipo.value = tipos.includes(tipoActual) ? tipoActual : '';
  }

  function getDispositivosFiltrados() {
    const q = searchInput.value.trim().toLowerCase();
    const tipo = filterTipo.value;
    const confiable = filterConfiable.value;

    return dispositivos.filter((d) => {
      const texto = [
        d.nombre_dispositivo || '',
        d.ip || '',
        d.mac || '',
      ].join(' ').toLowerCase();

      const cumpleBusqueda = !q || texto.includes(q);
      const cumpleTipo = !tipo || (d.tipo_dispositivo || 'Desconocido') === tipo;

      let cumpleConfiable = true;
      if (confiable === 'true') cumpleConfiable = !!d.es_confiable;
      if (confiable === 'false') cumpleConfiable = !d.es_confiable;

      return cumpleBusqueda && cumpleTipo && cumpleConfiable;
    });
  }

  function renderTabla() {
    const filtrados = getDispositivosFiltrados();
    tablaBody.innerHTML = '';

    if (!filtrados.length) {
      tablaBody.innerHTML = `
        <tr>
          <td colspan="8" class="text-center text-muted py-4">No hay dispositivos para mostrar</td>
        </tr>
      `;
      return;
    }

    filtrados.forEach((d) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${escapeHtml(d.nombre_dispositivo || 'Sin nombre')}</td>
        <td>${escapeHtml(d.ip || '-')}</td>
        <td>${escapeHtml(d.mac || '-')}</td>
        <td>
          <span class="badge ${d.estado === 'activo' ? 'bg-success' : 'bg-secondary'}">
            ${escapeHtml(d.estado || 'desconocido')}
          </span>
        </td>
        <td>${escapeHtml(d.tipo_dispositivo || 'Desconocido')}</td>
        <td>
          <div class="form-check form-switch">
            <input class="form-check-input confiable-switch" type="checkbox" data-mac="${escapeHtmlAttr(d.mac || '')}" ${d.es_confiable ? 'checked' : ''}>
          </div>
        </td>
        <td>${formatearFecha(d.ultima_detectado)}</td>
        <td>
          <button class="btn btn-sm btn-outline-primary btn-nota" data-mac="${escapeHtmlAttr(d.mac || '')}" data-nota="${escapeHtmlAttr(d.notas || '')}">
            <i class="bi bi-pencil-square"></i>
          </button>
        </td>
      `;
      tablaBody.appendChild(tr);
    });

    document.querySelectorAll('.confiable-switch').forEach((input) => {
      input.addEventListener('change', async (e) => {
        const mac = e.target.dataset.mac;
        const checked = e.target.checked;
        try {
          await fetchJson('/api/dispositivos/confiabilidad', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mac, es_confiable: checked }),
          });
          const item = dispositivos.find((x) => x.mac === mac);
          if (item) item.es_confiable = checked;
          mostrarToast('Confiabilidad actualizada', 'success');
        } catch (error) {
          e.target.checked = !checked;
          mostrarToast(error.message || 'No se pudo actualizar la confiabilidad', 'danger');
        }
      });
    });

    document.querySelectorAll('.btn-nota').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.getElementById('nota-mac').value = btn.dataset.mac;
        document.getElementById('nota-texto').value = btn.dataset.nota || '';
        notaModal.show();
      });
    });
  }

  async function guardarNota() {
    const mac = document.getElementById('nota-mac').value;
    const nota = document.getElementById('nota-texto').value;

    try {
      await fetchJson('/api/dispositivos/nota', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mac, nota }),
      });

      const item = dispositivos.find((x) => x.mac === mac);
      if (item) item.notas = nota;

      notaModal.hide();
      renderTabla();
      mostrarToast('Nota guardada', 'success');
    } catch (error) {
      console.error(error);
      mostrarToast(error.message || 'No se pudo guardar la nota', 'danger');
    }
  }

  async function cargarAlertas() {
    try {
      const data = await fetchJson('/api/alertas');
      const alertas = Array.isArray(data.alertas) ? data.alertas : [];
      actualizarBadgeAlertas(alertas.length);
      return alertas;
    } catch (error) {
      console.error('Error cargando alertas:', error);
      actualizarBadgeAlertas(0);
      return [];
    }
  }

  function actualizarBadgeAlertas(cantidad) {
    badgeAlertas.textContent = cantidad;
    badgeAlertas.classList.toggle('d-none', cantidad <= 0);
  }

  async function mostrarAlertas() {
    const contenedor = document.getElementById('contenido-alertas');
    contenedor.innerHTML = '<div class="text-center py-3">Cargando alertas...</div>';

    try {
      const data = await fetchJson('/api/alertas');
      const alertas = Array.isArray(data.alertas) ? data.alertas : [];

      if (!alertas.length) {
        contenedor.innerHTML = '<div class="text-center text-muted py-4">No hay alertas pendientes</div>';
      } else {
        contenedor.innerHTML = alertas.map((a) => `
          <div class="border rounded p-3 mb-3">
            <div class="d-flex justify-content-between align-items-start">
              <div>
                <h6 class="mb-1">${escapeHtml(a.tipo || 'Alerta')}</h6>
                <p class="mb-1">${escapeHtml(a.mensaje || '')}</p>
                <small class="text-muted">IP: ${escapeHtml(a.ip || '-')} | MAC: ${escapeHtml(a.mac || '-')}</small>
              </div>
              <small class="text-muted ms-3">${formatearFecha(a.fecha)}</small>
            </div>
          </div>
        `).join('');
      }

      alertasModal.show();
    } catch (error) {
      contenedor.innerHTML = '<div class="text-danger py-4">No se pudieron cargar las alertas</div>';
      alertasModal.show();
    }
  }

  async function cargarEstadisticas() {
    try {
      const data = await fetchJson('/api/estadisticas');
      const total = Array.isArray(data.total_dispositivos) ? (data.total_dispositivos[0]?.total || 0) : 0;
      const porEstado = Array.isArray(data.dispositivos_por_estado) ? data.dispositivos_por_estado : [];

      const activos = porEstado.find((x) => x.estado === 'activo')?.cantidad || 0;
      const inactivos = porEstado
        .filter((x) => x.estado !== 'activo')
        .reduce((acc, cur) => acc + (cur.cantidad || 0), 0);

      document.getElementById('stat-total').textContent = total;
      document.getElementById('stat-activos').textContent = activos;
      document.getElementById('stat-inactivos').textContent = inactivos;
    } catch (error) {
      console.error('Error cargando estadísticas:', error);
    }
  }

  function formatearFecha(value) {
    if (!value) return '-';
    const fecha = new Date(value);
    if (Number.isNaN(fecha.getTime())) return value;
    return fecha.toLocaleString('es-EC');
  }

  function mostrarToast(message, type = 'success') {
    const wrapper = document.createElement('div');
    wrapper.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    wrapper.style.top = '20px';
    wrapper.style.right = '20px';
    wrapper.style.zIndex = '2000';
    wrapper.style.minWidth = '280px';
    wrapper.role = 'alert';
    wrapper.innerHTML = `
      ${escapeHtml(message)}
      <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(wrapper);
    setTimeout(() => wrapper.remove(), 3500);
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  function escapeHtmlAttr(value) {
    return escapeHtml(value);
  }
});