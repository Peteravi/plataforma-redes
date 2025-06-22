// frontend/js/escaneo_automatico.js

document.addEventListener('DOMContentLoaded', () => {
  const fechaInput = document.getElementById('fecha-escaneo');
  const tipoSelect = document.getElementById('tipo-escaneo');
  const repetirSelect = document.getElementById('repetir-escaneo');
  const btnProgramar = document.getElementById('programar-escaneo-btn');

  // Configurar fecha mínima (ahora +5 min)
  const now = new Date();
  now.setMinutes(now.getMinutes() + 5);
  fechaInput.min = now.toISOString().slice(0,16);

  // Valor por defecto (ahora +10 min)
  const defaultDate = new Date();
  defaultDate.setMinutes(defaultDate.getMinutes() + 10);
  fechaInput.value = new Date(defaultDate.getTime() - defaultDate.getTimezoneOffset()*60000)
    .toISOString().slice(0,16);

  // Mostrar resumen inicial y cargar tabla
  actualizarResumen();
  cargarEscaneosProgramados();

  // Listeners de formulario
  tipoSelect.addEventListener('change', actualizarResumen);
  fechaInput.addEventListener('change', actualizarResumen);
  repetirSelect.addEventListener('change', actualizarResumen);
  btnProgramar.addEventListener('click', programarEscaneo);
});

/**
 * Actualiza el resumen dinámico de programación.
 */
function actualizarResumen() {
  const tipo = document.getElementById('tipo-escaneo').value;
  const fecha = new Date(document.getElementById('fecha-escaneo').value);
  const repetir = document.getElementById('repetir-escaneo').value;

  const options = { weekday:'long', year:'numeric', month:'long', day:'numeric', hour:'2-digit', minute:'2-digit' };
  const repText = {
    'diario': 'Diariamente',
    'semanal': 'Semanalmente',
    'mensual': 'Mensualmente',
    'una_vez': 'Una vez'
  }[repetir] || 'Una vez';

  const tipoText = {
    'completo': 'Completo',
    'rapido'  : 'Rápido',
    'personalizado': 'Personalizado'
  }[tipo] || tipo;

  document.getElementById('resumen-escaneo').innerHTML = `
    <div class="resumen-item">
      <span>Tipo de Escaneo:</span>
      <strong>${tipoText}</strong>
    </div>
    <div class="resumen-item">
      <span>Fecha Programada:</span>
      <strong>${fecha.toLocaleDateString('es-ES', options)}</strong>
    </div>
    <div class="resumen-item">
      <span>Repetición:</span>
      <strong>${repText}</strong>
    </div>
  `;
}

/**
 * Programa un nuevo escaneo y refresca la tabla sin recargar la página.
 */
async function programarEscaneo() {
  const tipo = document.getElementById('tipo-escaneo').value;
  const fechaLocal = new Date(document.getElementById('fecha-escaneo').value);
  const repetir = document.getElementById('repetir-escaneo').value;

  if (!fechaLocal || isNaN(fechaLocal)) {
    mostrarAlerta('Error', 'Selecciona una fecha válida', 'danger');
    return;
  }

  // Convertir a ISO sin offset
  const fechaUTC = new Date(fechaLocal.getTime() - fechaLocal.getTimezoneOffset()*60000);
  const iso = fechaUTC.toISOString().slice(0,16);

  const btn = document.getElementById('programar-escaneo-btn');
  const origText = btn.innerHTML;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Programando...';
  btn.disabled = true;

  try {
    const res = await fetch('/api/escaneos/programar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tipo, fecha_programada: iso, repeticion: repetir })
    });
    const data = await res.json();
    if (!res.ok || data.status !== 'success') throw new Error(data.message || 'Error al programar');

    mostrarAlerta('Éxito', 'Escaneo programado correctamente', 'success');
    await cargarEscaneosProgramados();

    // Reset formulario (+10 min)
    const next = new Date();
    next.setMinutes(next.getMinutes() + 10);
    const defISO = new Date(next.getTime() - next.getTimezoneOffset()*60000)
      .toISOString().slice(0,16);
    document.getElementById('fecha-escaneo').value = defISO;
    document.getElementById('repetir-escaneo').value = 'una_vez';
    actualizarResumen();
  } catch (error) {
    console.error('Error al programar escaneo:', error);
    const msg = error.message.includes('futura')
      ? 'La fecha debe estar en el futuro'
      : error.message;
    mostrarAlerta('Error', msg, 'danger');
  } finally {
    btn.innerHTML = origText;
    btn.disabled = false;
  }
}

/**
 * Solicita y renderiza la lista de escaneos programados.
 */
async function cargarEscaneosProgramados() {
  try {
    const res = await fetch('/api/escaneos/programados');
    const data = await res.json();

    const tbody = document.querySelector('#tabla-escaneos tbody');
    tbody.innerHTML = '';

    if (data.status === 'success' && data.escaneos.length) {
      data.escaneos.forEach(e => {
        const f = new Date(e.fecha_programada);
        const row = document.createElement('tr');
        row.innerHTML = `
          <td>${{completo:'Completo',rapido:'Rápido',personalizado:'Personalizado'}[e.tipo] || e.tipo}</td>
          <td>${f.toLocaleString()}</td>
          <td>${formatearRepeticion(e.repeticion)}</td>
          <td><span class="estado-${e.estado}">${formatearEstado(e.estado)}</span></td>
          <td>
            <button class="btn btn-sm btn-outline-danger cancelar-escaneo" data-id="${e.id}">
              <i class="bi bi-x-circle"></i> Cancelar
            </button>
          </td>`;
        tbody.appendChild(row);
      });
      document.querySelectorAll('.cancelar-escaneo').forEach(btn => {
        btn.addEventListener('click', () => mostrarConfirmacionCancelacion(btn.dataset.id));
      });
    } else {
      tbody.innerHTML = `
        <tr><td colspan="5" class="text-center text-muted py-4">No hay escaneos programados</td></tr>`;
    }
  } catch (err) {
    console.error('Error al cargar escaneos programados:', err);
    mostrarAlerta('Error', 'No se pudieron cargar los escaneos programados', 'danger');
  }
}

/** Formatea la repetición en texto legible */
function formatearRepeticion(rep) {
  return { diario:'Diario', semanal:'Semanal', mensual:'Mensual', una_vez:'Una vez' }[rep] || rep;
}

/** Formatea el estado */
function formatearEstado(est) {
  return { pendiente:'Pendiente', ejecutando:'En progreso', completado:'Completado', cancelado:'Cancelado' }[est] || est;
}

/** Muestra un modal de confirmación para cancelar */
function mostrarConfirmacionCancelacion(id) {
  const modalEl = document.getElementById('confirmacionModal');
  const modal = new bootstrap.Modal(modalEl);
  document.getElementById('confirmacion-texto').innerHTML = `¿Confirmar cancelación del escaneo?`;
  const btn = modalEl.querySelector('#confirmar-accion');
  btn.replaceWith(btn.cloneNode(true));
  modalEl.querySelector('#confirmar-accion').addEventListener('click', async () => {
    try {
      const res = await fetch(`/api/escaneos/cancelar/${id}`, { method:'POST' });
      const data = await res.json();
      if (data.status==='success') {
        mostrarAlerta('Éxito','Escaneo cancelado','success');
        await cargarEscaneosProgramados();
        modal.hide();
      } else {
        throw new Error(data.message);
      }
    } catch (e) {
      console.error(e);
      mostrarAlerta('Error', e.message, 'danger');
    }
  });
  modal.show();
}

/** Inserta una alerta en pantalla */
function mostrarAlerta(titulo, msg, tipo) {
  const container = document.querySelector('main.container-fluid');
  const alert = document.createElement('div');
  alert.className = `alert alert-${tipo} alert-dismissible fade show`;
  alert.role = 'alert';
  alert.innerHTML = `
    <strong>${titulo}:</strong> ${msg}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
  container.prepend(alert);
  setTimeout(() => alert.remove(), 5000);
}
