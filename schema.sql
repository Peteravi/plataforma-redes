CREATE DATABASE IF NOT EXISTS plataforma_redes;
USE plataforma_redes;

-- =========================
-- TABLA DISPOSITIVOS
-- =========================
CREATE TABLE dispositivos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ip VARCHAR(50),
    mac VARCHAR(50) UNIQUE,
    nombre_dispositivo VARCHAR(100),
    tipo_dispositivo VARCHAR(50) DEFAULT 'Desconocido',
    estado VARCHAR(20) DEFAULT 'activo',
    confianza BOOLEAN DEFAULT FALSE,
    ultima_detectado DATETIME,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- TABLA ESCANEOS
-- =========================
CREATE TABLE escaneos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- LOGS DE DISPOSITIVOS
-- =========================
CREATE TABLE logs_dispositivos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dispositivo_id INT,
    escaneo_id INT,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id) ON DELETE CASCADE,
    FOREIGN KEY (escaneo_id) REFERENCES escaneos(id) ON DELETE CASCADE
);

-- =========================
-- ESCANEOS PROGRAMADOS
-- =========================
CREATE TABLE escaneos_programados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fecha_programada DATETIME,
    repeticion VARCHAR(20), -- diaria, semanal, mensual
    estado VARCHAR(20) DEFAULT 'pendiente'
);

-- =========================
-- ALERTAS
-- =========================
CREATE TABLE alertas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dispositivo_id INT,
    tipo_alerta VARCHAR(50),
    mensaje TEXT,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id) ON DELETE CASCADE
);