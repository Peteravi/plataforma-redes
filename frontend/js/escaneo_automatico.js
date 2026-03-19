document.addEventListener('DOMContentLoaded', () => {
  const tipo = document.getElementById('tipo-escaneo');
  const fecha = document.getElementById('fecha-escaneo');
  const repetir = document.getElementById('repetir-escaneo');
  const btnProgramar = document.getElementById('btn-programar');

  establecerFechaMinima();
  actualizarResumen();
  cargarEscaneosProgramados();

  tipo.addEventListener('change', actualizarResumen);
  fecha.addEventListener('change', actualizarResumen);
  repetir.addEventListener('change', actualizarResumen);
  btnProgramar.addEventListener('click', programarEscaneo);

  function establecerFechaMinima() {
    const ahora = new Date();
    ahora.setMinutes(ahora.getMinutes() - ahora.getTimezoneOffset());
    const min = ahora.toISOString().slice(0, 16);
    fecha.min = min;

    if (!fecha.value || fecha.value < min) {
      const futuro = new Date(Date.now() + 10 * 60 * 1000);
      futuro.setMinutes(futuro.getMinutes() - futuro.getTimezoneOffset());
      fecha.value = futuro.toISOString().slice(0, 16);
    }
  }

  function actualizarResumen() {
    const fechaLocal = new Date(fecha.value);
    if (!fecha.value || Number.isNaN(fechaLocal.getTime())) {
      document.getElementById('resumen-escaneo').innerHTML = '<span class="text-muted">Completa los datos del escaneo.</span>';
      return;
    }

    const repText = formatearRepeticion(repetir.value);
    const tipoText = { completo: 'Completo', rapido: 'Rápido', personalizado: 'Personalizado' }[tipo.value] || tipo.value;
    const options = { dateStyle: 'full', timeStyle: 'short' };

    document.getElementById('resumen-escaneo').innerHTML = `
      <div class="resumen-item mb-2"><span>Tipo de Escaneo:</span> <strong>${tipoText}</strong></div>
      <div class="resumen-item mb-2"><span>Fecha Programada:</span> <strong>${fechaLocal.toLocaleString('es-EC', options)}</strong></div>
      <div class="resumen-item"><span>Repetición:</span> <strong>${repText}</strong></div>
    `;
  }

  async function programarEscaneo() {
    const fechaLocal = new Date(fecha.value);
    if (!fecha.value || Number.isNaN(fechaLocal.getTime())) {
      mostrarAlerta('Error', 'Selecciona una fecha válida', 'danger');
      return;
    }
    if (fechaLocal <= new Date()) {
      mostrarAlerta('Error', 'La fecha debe estar en el futuro', 'danger');
      return;
    }

    const originalText = btnProgramar.innerHTML;
    btnProgramar.disabled = true;
    btnProgramar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Programando...';

    try {
      const iso = new Date(fechaLocal.getTime() - fechaLocal.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
      const res = await fetch('/api/escaneos/programar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tipo: tipo.value,
          fecha_programada: iso,
          repeticion: repetir.value,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.status !== 'success') throw new Error(data.message || 'Error al programar');

      mostrarAlerta('Éxito', 'Escaneo programado correctamente', 'success');
      establecerFechaMinima();
      repetir.value = 'una_vez';
      actualizarResumen();
      await cargarEscaneosProgramados();
    } catch (error) {
      console.error('Error al programar escaneo:', error);
      mostrarAlerta('Error', error.message || 'No se pudo programar el escaneo', 'danger');
    } finally {
      btnProgramar.disabled = false;
      btnProgramar.innerHTML = originalText;
    }
  }

  async function cargarEscaneosProgramados() {
    try {
      const res = await fetch('/api/escaneos/programados');
      const data = await res.json();
      const tbody = document.querySelector('#tabla-escaneos tbody');
      tbody.innerHTML = '';

      if (data.status === 'success' && Array.isArray(data.escaneos) && data.escaneos.length) {
        data.escaneos.forEach((item) => {
          const f = new Date(item.fecha_programada);
          const row = document.createElement('tr');
          row.innerHTML = `
            <td>${({ completo: 'Completo', rapido: 'Rápido', personalizado: 'Personalizado' }[item.tipo] || item.tipo)}</td>
            <td>${Number.isNaN(f.getTime()) ? item.fecha_programada : f.toLocaleString('es-EC')}</td>
            <td>${formatearRepeticion(item.repeticion)}</td>
            <td><span class="estado-${item.estado}">${formatearEstado(item.estado)}</span></td>
            <td>
              <button class="btn btn-sm btn-outline-danger cancelar-escaneo" data-id="${item.id}">
                <i class="bi bi-x-circle"></i> Cancelar
              </button>
            </td>
          `;
          tbody.appendChild(row);
        });

        document.querySelectorAll('.cancelar-escaneo').forEach((button) => {
          button.addEventListener('click', () => mostrarConfirmacionCancelacion(button.dataset.id));
        });
      } else {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No hay escaneos programados</td></tr>';
      }
    } catch (err) {
      console.error('Error al cargar escaneos programados:', err);
      mostrarAlerta('Error', 'No se pudieron cargar los escaneos programados', 'danger');
    }
  }

  function formatearRepeticion(rep) {
    return { diario: 'Diario', semanal: 'Semanal', mensual: 'Mensual', una_vez: 'Una vez' }[rep] || rep;
  }

  function formatearEstado(est) {
    return { pendiente: 'Pendiente', ejecutando: 'En progreso', completado: 'Completado', cancelado: 'Cancelado' }[est] || est;
  }

  function mostrarConfirmacionCancelacion(id) {
    const modalEl = document.getElementById('confirmacionModal');
    const modal = new bootstrap.Modal(modalEl);
    document.getElementById('confirmacion-texto').textContent = '¿Confirmar cancelación del escaneo?';

    const nuevoBtn = document.getElementById('confirmar-accion').cloneNode(true);
    document.getElementById('confirmar-accion').replaceWith(nuevoBtn);
    nuevoBtn.addEventListener('click', async () => {
      try {
        const res = await fetch(`/api/escaneos/cancelar/${id}`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok || data.status !== 'success') throw new Error(data.message || 'No se pudo cancelar');
        mostrarAlerta('Éxito', 'Escaneo cancelado', 'success');
        modal.hide();
        await cargarEscaneosProgramados();
      } catch (error) {
        console.error(error);
        mostrarAlerta('Error', error.message || 'No se pudo cancelar el escaneo', 'danger');
      }
    });

    modal.show();
  }

  function mostrarAlerta(titulo, msg, tipo) {
    const container = document.querySelector('main.container-fluid');
    const alert = document.createElement('div');
    alert.className = `alert alert-${tipo} alert-dismissible fade show`;
    alert.role = 'alert';
    alert.innerHTML = `<strong>${titulo}:</strong> ${msg}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    container.prepend(alert);
    setTimeout(() => alert.remove(), 5000);
  }
});