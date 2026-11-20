-- Creación de la Base de Datos
CREATE DATABASE reserva_cancha;
GO

USE reserva_cancha;
GO

-- 1. EMPRESAS
CREATE TABLE EMPRESAS (
    id_empresa INT IDENTITY(1,1) PRIMARY KEY,
    nombre_fiscal VARCHAR(150) NOT NULL,
    rtn_nit VARCHAR(30) NOT NULL UNIQUE,
    correo_contacto VARCHAR(120) NOT NULL,
    fecha_creacion DATETIME2 DEFAULT GETDATE()
);
GO

-- 2. SUCURSALES
CREATE TABLE SUCURSALES (
    id_sucursal INT IDENTITY(1,1) PRIMARY KEY,
    id_empresa INT NOT NULL,
    nombre_sucursal VARCHAR(120) NOT NULL,
    direccion NVARCHAR(MAX) NOT NULL,
    telefono VARCHAR(25) NOT NULL,
    activa BIT DEFAULT 1,
    CONSTRAINT FK_Sucursal_Empresa FOREIGN KEY (id_empresa) REFERENCES EMPRESAS(id_empresa)
);
GO

-- 3. TIPOS DE CANCHA
CREATE TABLE TIPOS_CANCHA (
    id_tipo_cancha INT IDENTITY(1,1) PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL UNIQUE,
    descripcion NVARCHAR(MAX)
);
GO

-- 4. CANCHAS
CREATE TABLE CANCHAS (
    id_cancha INT IDENTITY(1,1) PRIMARY KEY,
    id_sucursal INT NOT NULL,
    id_tipo_cancha INT NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    ubicacion_interna VARCHAR(120),
    precio_hora DECIMAL(10, 2) NOT NULL,
    activa BIT DEFAULT 1,
    CONSTRAINT FK_Cancha_Sucursal FOREIGN KEY (id_sucursal) REFERENCES SUCURSALES(id_sucursal),
    CONSTRAINT FK_Cancha_Tipo FOREIGN KEY (id_tipo_cancha) REFERENCES TIPOS_CANCHA(id_tipo_cancha)
);
GO

-- 5. CLIENTES (Nombres atómicos en 3FN)
CREATE TABLE CLIENTES (
    id_cliente INT IDENTITY(1,1) PRIMARY KEY,
    primer_nombre VARCHAR(50) NOT NULL,
    segundo_nombre VARCHAR(50) NULL,
    primer_apellido VARCHAR(50) NOT NULL,
    segundo_apellido VARCHAR(50) NULL,
    telefono VARCHAR(25) NOT NULL,
    correo VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    fecha_registro DATETIME2 DEFAULT GETDATE()
);
GO

-- 6. HORARIOS POR SUCURSAL
CREATE TABLE HORARIOS (
    id_horario INT IDENTITY(1,1) PRIMARY KEY,
    id_sucursal INT NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    CONSTRAINT FK_Horario_Sucursal FOREIGN KEY (id_sucursal) REFERENCES SUCURSALES(id_sucursal) ON DELETE CASCADE,
    CONSTRAINT uk_sucursal_bloque UNIQUE (id_sucursal, hora_inicio, hora_fin)
);
GO

-- 7. ROLES ADMINISTRATIVOS
CREATE TABLE ROLES_ADMIN (
    id_rol INT IDENTITY(1,1) PRIMARY KEY,
    nombre_rol VARCHAR(50) NOT NULL UNIQUE,
    descripcion NVARCHAR(MAX)
);
GO

-- 8. USUARIOS ADMINISTRADORES (Nombres atómicos)
CREATE TABLE USUARIOS_ADMINISTRADORES (
    id_usuario INT IDENTITY(1,1) PRIMARY KEY,
    id_sucursal INT NULL, -- NULL indica Administrador General de la empresa
    id_rol INT NOT NULL,
    primer_nombre VARCHAR(50) NOT NULL,
    segundo_nombre VARCHAR(50) NULL,
    primer_apellido VARCHAR(50) NOT NULL,
    segundo_apellido VARCHAR(50) NULL,
    correo VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    activo BIT DEFAULT 1,
    CONSTRAINT FK_Admin_Sucursal FOREIGN KEY (id_sucursal) REFERENCES SUCURSALES(id_sucursal) ON DELETE SET NULL,
    CONSTRAINT FK_Admin_Rol FOREIGN KEY (id_rol) REFERENCES ROLES_ADMIN(id_rol)
);
GO

-- 9. ESTADOS DE RESERVA (Tabla catálogo normalizada en 3FN)
CREATE TABLE ESTADOS_RESERVA (
    id_estado_reserva INT IDENTITY(1,1) PRIMARY KEY,
    nombre_estado VARCHAR(30) NOT NULL UNIQUE, -- Ej: pendiente, confirmada, cancelada
    descripcion NVARCHAR(MAX),
    ocupa_horario BIT NOT NULL DEFAULT 1, -- 1 para pendiente/confirmada, 0 para cancelada
    activo BIT NOT NULL DEFAULT 1
);
GO

-- 10. RESERVAS
CREATE TABLE RESERVAS (
    id_reserva INT IDENTITY(1,1) PRIMARY KEY,
    id_cliente INT NOT NULL,
    id_cancha INT NOT NULL,
    id_horario INT NOT NULL,
    id_estado_reserva INT NOT NULL,
    fecha_reserva DATE NOT NULL,
    fecha_registro DATETIME2 DEFAULT GETDATE(),
    monto_acordado DECIMAL(10, 2) NOT NULL,
    CONSTRAINT FK_Reserva_Cliente FOREIGN KEY (id_cliente) REFERENCES CLIENTES(id_cliente),
    CONSTRAINT FK_Reserva_Cancha FOREIGN KEY (id_cancha) REFERENCES CANCHAS(id_cancha),
    CONSTRAINT FK_Reserva_Horario FOREIGN KEY (id_horario) REFERENCES HORARIOS(id_horario),
    CONSTRAINT FK_Reserva_Estado FOREIGN KEY (id_estado_reserva) REFERENCES ESTADOS_RESERVA(id_estado_reserva)
);
GO

-- VISTA INDEXADA PARA EVITAR DOBLE RESERVA ACTIVA (PENDIENTE / CONFIRMADA)
CREATE VIEW dbo.vw_reservas_activas_bloqueo
WITH SCHEMABINDING
AS
SELECT 
    r.id_reserva,
    r.id_cancha,
    r.fecha_reserva,
    r.id_horario
FROM dbo.RESERVAS r
INNER JOIN dbo.ESTADOS_RESERVA er ON r.id_estado_reserva = er.id_estado_reserva
WHERE er.nombre_estado IN ('pendiente', 'confirmada');
GO

SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET ANSI_NULLS ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET NUMERIC_ROUNDABORT OFF;
GO

CREATE UNIQUE CLUSTERED INDEX ix_uq_reserva_activa
ON dbo.vw_reservas_activas_bloqueo (id_cancha, fecha_reserva, id_horario);
GO

-- 11. HISTORIAL DE RESERVAS (Auditoría específica referenciando ESTADOS_RESERVA)
CREATE TABLE HISTORIAL_RESERVAS (
    id_historial INT IDENTITY(1,1) PRIMARY KEY,
    id_reserva INT NOT NULL,
    id_usuario_admin INT NULL, -- NULL si el cambio lo hizo el cliente
    id_estado_anterior INT NULL, -- NULL cuando se crea la reserva
    id_estado_nuevo INT NOT NULL,
    fecha_anterior DATE NULL,
    fecha_nueva DATE NULL,
    id_horario_anterior INT NULL,
    id_horario_nuevo INT NULL,
    motivo_cambio NVARCHAR(MAX) NOT NULL,
    fecha_cambio DATETIME2 DEFAULT GETDATE(),
    CONSTRAINT FK_Historial_Reserva FOREIGN KEY (id_reserva) REFERENCES RESERVAS(id_reserva) ON DELETE CASCADE,
    CONSTRAINT FK_Historial_Admin FOREIGN KEY (id_usuario_admin) REFERENCES USUARIOS_ADMINISTRADORES(id_usuario) ON DELETE SET NULL,
    CONSTRAINT FK_Historial_EstadoAnt FOREIGN KEY (id_estado_anterior) REFERENCES ESTADOS_RESERVA(id_estado_reserva),
    CONSTRAINT FK_Historial_EstadoNuevo FOREIGN KEY (id_estado_nuevo) REFERENCES ESTADOS_RESERVA(id_estado_reserva),
    CONSTRAINT FK_Historial_HAnterior FOREIGN KEY (id_horario_anterior) REFERENCES HORARIOS(id_horario),
    CONSTRAINT FK_Historial_HNuevo FOREIGN KEY (id_horario_nuevo) REFERENCES HORARIOS(id_horario)
);
GO

-- 12. MÉTODOS DE PAGO
CREATE TABLE METODOS_PAGO (
    id_metodo_pago INT IDENTITY(1,1) PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE, -- Efectivo, Transferencia, Tarjeta
    descripcion NVARCHAR(MAX),
    activo BIT DEFAULT 1
);
GO

-- 13. ESTADOS DE PAGO
CREATE TABLE ESTADOS_PAGO (
    id_estado_pago INT IDENTITY(1,1) PRIMARY KEY,
    nombre_estado VARCHAR(50) NOT NULL UNIQUE,
    descripcion NVARCHAR(MAX)
);
GO

-- 14. COMPROBANTES DE PAGO
CREATE TABLE COMPROBANTES_PAGO (
    id_comprobante INT IDENTITY(1,1) PRIMARY KEY,
    numero_autorizacion VARCHAR(100) NOT NULL,
    banco_emisor VARCHAR(100) NULL,
    imagen_voucher_url VARCHAR(255) NULL
);
GO

-- 15. PAGOS
CREATE TABLE PAGOS (
    id_pago INT IDENTITY(1,1) PRIMARY KEY,
    id_reserva INT NOT NULL,
    id_metodo_pago INT NOT NULL,
    id_estado_pago INT NOT NULL,
    id_comprobante INT NULL,
    id_usuario_admin INT NOT NULL,
    monto DECIMAL(10, 2) NOT NULL,
    fecha_pago DATETIME2 DEFAULT GETDATE(),
    CONSTRAINT FK_Pago_Reserva FOREIGN KEY (id_reserva) REFERENCES RESERVAS(id_reserva),
    CONSTRAINT FK_Pago_Metodo FOREIGN KEY (id_metodo_pago) REFERENCES METODOS_PAGO(id_metodo_pago),
    CONSTRAINT FK_Pago_Estado FOREIGN KEY (id_estado_pago) REFERENCES ESTADOS_PAGO(id_estado_pago),
    CONSTRAINT FK_Pago_Comprobante FOREIGN KEY (id_comprobante) REFERENCES COMPROBANTES_PAGO(id_comprobante),
    CONSTRAINT FK_Pago_Admin FOREIGN KEY (id_usuario_admin) REFERENCES USUARIOS_ADMINISTRADORES(id_usuario)
);
GO

-- VISTA PARA ESTADO DE CUENTA Y SALDOS
CREATE VIEW dbo.vw_estado_cuenta_reservas AS
SELECT 
    r.id_reserva,
    s.nombre_sucursal,
    c.nombre AS cancha,
    CONCAT(cl.primer_nombre, ' ', ISNULL(cl.segundo_nombre + ' ', ''), cl.primer_apellido, ' ', ISNULL(cl.segundo_apellido, '')) AS cliente_nombre,
    r.fecha_reserva,
    h.hora_inicio,
    h.hora_fin,
    er.nombre_estado AS estado,
    r.monto_acordado,
    ISNULL(SUM(CASE WHEN ep.nombre_estado = 'Aprobado' THEN p.monto ELSE 0 END), 0) AS total_pagado,
    (r.monto_acordado - ISNULL(SUM(CASE WHEN ep.nombre_estado = 'Aprobado' THEN p.monto ELSE 0 END), 0)) AS saldo_pendiente
FROM dbo.RESERVAS r
JOIN dbo.ESTADOS_RESERVA er ON r.id_estado_reserva = er.id_estado_reserva
JOIN dbo.CANCHAS c ON r.id_cancha = c.id_cancha
JOIN dbo.SUCURSALES s ON c.id_sucursal = s.id_sucursal
JOIN dbo.CLIENTES cl ON r.id_cliente = cl.id_cliente
JOIN dbo.HORARIOS h ON r.id_horario = h.id_horario
LEFT JOIN dbo.PAGOS p ON r.id_reserva = p.id_reserva
LEFT JOIN dbo.ESTADOS_PAGO ep ON p.id_estado_pago = ep.id_estado_pago
GROUP BY r.id_reserva, s.nombre_sucursal, c.nombre, cl.primer_nombre, cl.segundo_nombre, 
         cl.primer_apellido, cl.segundo_apellido, r.fecha_reserva, h.hora_inicio, h.hora_fin, 
         er.nombre_estado, r.monto_acordado;
GO

-- DATOS INICIALES DE PRUEBA
INSERT INTO ESTADOS_RESERVA (nombre_estado, descripcion, ocupa_horario, activo) VALUES
('pendiente', 'Reserva solicitada en espera de confirmación o pago inicial', 1, 1),
('confirmada', 'Reserva confirmada y bloqueada para el cliente', 1, 1),
('cancelada', 'Reserva cancelada; el horario queda disponible nuevamente', 0, 1);

INSERT INTO EMPRESAS (nombre_fiscal, rtn_nit, correo_contacto) 
VALUES ('Complejos Deportivos del Centro S.A.', '08011990123456', 'contacto@complejos.hn');

INSERT INTO SUCURSALES (id_empresa, nombre_sucursal, direccion, telefono) 
VALUES (1, 'Sede Boulevard Morazán', 'Tegucigalpa, Col. Palmira', '2232-0000'),
       (1, 'Sede Anillo Periférico', 'Tegucigalpa, Sector Sur', '2232-1111');

INSERT INTO TIPOS_CANCHA (nombre, descripcion) 
VALUES ('Fútbol 7', 'Cancha sintética techada para 14 jugadores'),
       ('Pádel', 'Cancha de cristal reglamentaria');

INSERT INTO CANCHAS (id_sucursal, id_tipo_cancha, nombre, ubicacion_interna, precio_hora) 
VALUES (1, 1, 'Cancha Sintética A1', 'Sector Norte Techado', 800.00),
       (1, 2, 'Pista Pádel Pro 1', 'Zona Exterior', 600.00),
       (2, 1, 'Cancha Principal Sur', 'Campo 1', 750.00);

INSERT INTO HORARIOS (id_sucursal, hora_inicio, hora_fin) 
VALUES (1, '16:00:00', '17:00:00'),
       (1, '17:00:00', '18:00:00'),
       (1, '18:00:00', '19:00:00'),
       (2, '16:00:00', '17:00:00');

INSERT INTO ROLES_ADMIN (nombre_rol, descripcion) 
VALUES ('Admin General', 'Acceso corporativo global'),
       ('Admin Sucursal', 'Gestión operativa de una sede');

INSERT INTO USUARIOS_ADMINISTRADORES (id_sucursal, id_rol, primer_nombre, primer_apellido, correo, password_hash) 
VALUES (1, 2, 'Carlos', 'Mendoza', 'admin@sede1.com', '123456');

INSERT INTO CLIENTES (primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, telefono, correo, password_hash) 
VALUES ('Juan', 'José', 'Pérez', 'López', '9988-7766', 'juan@correo.com', '123456');

INSERT INTO METODOS_PAGO (nombre, descripcion) 
VALUES ('Efectivo', 'Pago en ventanilla'),
       ('Transferencia', 'Transferencia bancaria directa'),
       ('Tarjeta', 'POS Débito / Crédito');

INSERT INTO ESTADOS_PAGO (nombre_estado, descripcion) 
VALUES ('Aprobado', 'Pago verificado y conciliado'),
       ('Pendiente Conciliación', 'En espera de validación bancaria');
GO


USE reserva_cancha;
GO

-- Verifica que exista el rol 'Admin General'
IF NOT EXISTS (SELECT 1 FROM dbo.ROLES_ADMIN WHERE nombre_rol = 'Admin General')
BEGIN
    INSERT INTO dbo.ROLES_ADMIN (nombre_rol, descripcion)
    VALUES ('Admin General', 'Acceso global a todas las sucursales y canchas');
END
GO

-- Crea el usuario Super Admin con id_sucursal = NULL (acceso global)
INSERT INTO dbo.USUARIOS_ADMINISTRADORES (
    id_sucursal, id_rol, primer_nombre, segundo_nombre,
    primer_apellido, segundo_apellido, correo, password_hash, activo
)
SELECT
    NULL,
    r.id_rol,
    'Super',
    NULL,
    'Admin',
    NULL,
    'superadmin@reservacancha.com',
    '123456',
    1
FROM dbo.ROLES_ADMIN r
WHERE r.nombre_rol = 'Admin General'
  AND NOT EXISTS (
      SELECT 1 FROM dbo.USUARIOS_ADMINISTRADORES
      WHERE LOWER(correo) = 'superadmin@reservacancha.com'
  );
GO


USE reserva_cancha;
GO

-- 1. Asegurar tipos de cancha (incluyendo Baloncesto)
IF NOT EXISTS (SELECT 1 FROM dbo.TIPOS_CANCHA WHERE nombre = 'Baloncesto')
BEGIN
    INSERT INTO dbo.TIPOS_CANCHA (nombre, descripcion)
    VALUES ('Baloncesto', 'Cancha multifuncional para partidos y entrenamientos de baloncesto');
END
GO

-- 2. Insertar nuevas sucursales (asumiendo id_empresa = 1)
IF NOT EXISTS (SELECT 1 FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Sede Centro Histórico')
BEGIN
    INSERT INTO dbo.SUCURSALES (id_empresa, nombre_sucursal, direccion, telefono, activa)
    VALUES (1, 'Sede Centro Histórico', 'Tegucigalpa, Barrio La Hoya', '2232-2200', 1);
END

IF NOT EXISTS (SELECT 1 FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Sede Valle de Ángeles')
BEGIN
    INSERT INTO dbo.SUCURSALES (id_empresa, nombre_sucursal, direccion, telefono, activa)
    VALUES (1, 'Sede Valle de Ángeles', 'Km 22 Carretera a Valle de Ángeles', '2232-3300', 1);
END
GO

-- 3. Insertar nuevas canchas en las sucursales existentes y nuevas
DECLARE @id_sede1 INT = (SELECT id_sucursal FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Sede Boulevard Morazán');
DECLARE @id_sede2 INT = (SELECT id_sucursal FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Sede Anillo Periférico');
DECLARE @id_sede3 INT = (SELECT id_sucursal FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Sede Centro Histórico');
DECLARE @id_sede4 INT = (SELECT id_sucursal FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Sede Valle de Ángeles');

DECLARE @id_fut7 INT = (SELECT id_tipo_cancha FROM dbo.TIPOS_CANCHA WHERE nombre = 'Fútbol 7');
DECLARE @id_padel INT = (SELECT id_tipo_cancha FROM dbo.TIPOS_CANCHA WHERE nombre = 'Pádel');
DECLARE @id_basket INT = (SELECT id_tipo_cancha FROM dbo.TIPOS_CANCHA WHERE nombre = 'Baloncesto');

-- Canchas adicionales en Sede 1
IF NOT EXISTS (SELECT 1 FROM dbo.CANCHAS WHERE nombre = 'Cancha Sintética A2' AND id_sucursal = @id_sede1)
    INSERT INTO dbo.CANCHAS (id_sucursal, id_tipo_cancha, nombre, ubicacion_interna, precio_hora, activa)
    VALUES (@id_sede1, @id_fut7, 'Cancha Sintética A2', 'Sector Sur Techado', 850.00, 1);

IF NOT EXISTS (SELECT 1 FROM dbo.CANCHAS WHERE nombre = 'Pista Pádel Pro 2' AND id_sucursal = @id_sede1)
    INSERT INTO dbo.CANCHAS (id_sucursal, id_tipo_cancha, nombre, ubicacion_interna, precio_hora, activa)
    VALUES (@id_sede1, @id_padel, 'Pista Pádel Pro 2', 'Zona Central', 650.00, 1);

-- Canchas adicionales en Sede 2
IF NOT EXISTS (SELECT 1 FROM dbo.CANCHAS WHERE nombre = 'Cancha Sur B2' AND id_sucursal = @id_sede2)
    INSERT INTO dbo.CANCHAS (id_sucursal, id_tipo_cancha, nombre, ubicacion_interna, precio_hora, activa)
    VALUES (@id_sede2, @id_fut7, 'Cancha Sur B2', 'Campo 2', 750.00, 1);

IF NOT EXISTS (SELECT 1 FROM dbo.CANCHAS WHERE nombre = 'Duela Baloncesto Sur 1' AND id_sucursal = @id_sede2)
    INSERT INTO dbo.CANCHAS (id_sucursal, id_tipo_cancha, nombre, ubicacion_interna, precio_hora, activa)
    VALUES (@id_sede2, @id_basket, 'Duela Baloncesto Sur 1', 'Polideportivo Este', 700.00, 1);

-- Canchas en Sede 3 (Centro Histórico)
IF NOT EXISTS (SELECT 1 FROM dbo.CANCHAS WHERE nombre = 'Cancha Central 1' AND id_sucursal = @id_sede3)
    INSERT INTO dbo.CANCHAS (id_sucursal, id_tipo_cancha, nombre, ubicacion_interna, precio_hora, activa)
    VALUES (@id_sede3, @id_fut7, 'Cancha Central 1', 'Nivel 1', 800.00, 1);

IF NOT EXISTS (SELECT 1 FROM dbo.CANCHAS WHERE nombre = 'Cancha Basket Centro' AND id_sucursal = @id_sede3)
    INSERT INTO dbo.CANCHAS (id_sucursal, id_tipo_cancha, nombre, ubicacion_interna, precio_hora, activa)
    VALUES (@id_sede3, @id_basket, 'Cancha Basket Centro', 'Gimnasio Principal', 650.00, 1);

-- Canchas en Sede 4 (Valle de Ángeles)
IF NOT EXISTS (SELECT 1 FROM dbo.CANCHAS WHERE nombre = 'Cancha Bosque Fútbol 1' AND id_sucursal = @id_sede4)
    INSERT INTO dbo.CANCHAS (id_sucursal, id_tipo_cancha, nombre, ubicacion_interna, precio_hora, activa)
    VALUES (@id_sede4, @id_fut7, 'Cancha Bosque Fútbol 1', 'Área Norte', 900.00, 1);

IF NOT EXISTS (SELECT 1 FROM dbo.CANCHAS WHERE nombre = 'Pista Pádel Mirador' AND id_sucursal = @id_sede4)
    INSERT INTO dbo.CANCHAS (id_sucursal, id_tipo_cancha, nombre, ubicacion_interna, precio_hora, activa)
    VALUES (@id_sede4, @id_padel, 'Pista Pádel Mirador', 'Terraza Este', 700.00, 1);
GO

-- 4. Insertar bloques horarios (respetando la restricción UNIQUE uk_sucursal_bloque)
DECLARE @sucursales TABLE (id_sucursal INT);
INSERT INTO @sucursales (id_sucursal)
SELECT id_sucursal FROM dbo.SUCURSALES WHERE activa = 1;

DECLARE @bloques TABLE (hora_inicio TIME, hora_fin TIME);
INSERT INTO @bloques (hora_inicio, hora_fin) VALUES
('08:00:00', '09:00:00'),
('09:00:00', '10:00:00'),
('10:00:00', '11:00:00'),
('14:00:00', '15:00:00'),
('15:00:00', '16:00:00'),
('16:00:00', '17:00:00'),
('17:00:00', '18:00:00'),
('18:00:00', '19:00:00'),
('19:00:00', '20:00:00'),
('20:00:00', '21:00:00');

INSERT INTO dbo.HORARIOS (id_sucursal, hora_inicio, hora_fin)
SELECT s.id_sucursal, b.hora_inicio, b.hora_fin
FROM @sucursales s
CROSS JOIN @bloques b
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.HORARIOS h
    WHERE h.id_sucursal = s.id_sucursal
      AND h.hora_inicio = b.hora_inicio
      AND h.hora_fin = b.hora_fin
);
GO

-- Verificación rápida de lo insertado
SELECT s.nombre_sucursal, COUNT(DISTINCT c.id_cancha) AS total_canchas, COUNT(DISTINCT h.id_horario) AS total_horarios
FROM dbo.SUCURSALES s
LEFT JOIN dbo.CANCHAS c ON s.id_sucursal = c.id_sucursal
LEFT JOIN dbo.HORARIOS h ON s.id_sucursal = h.id_sucursal
GROUP BY s.id_sucursal, s.nombre_sucursal
ORDER BY s.id_sucursal;
GO

USE reserva_cancha

select primer_nombre, correo from CLIENTES

--CAMBIO PARA QUE EL QEUDE REGISTRADO EL CAMBIO DEL CLIENTE DEL PAGO
USE reserva_cancha
ALTER TABLE dbo.PAGOS
ALTER COLUMN id_usuario_admin INT NULL;


--mas registros de sucursales y empresas como de clietes
USE reserva_cancha;
GO

-- ============================================================================
-- 1. NUEVAS EMPRESAS
-- ============================================================================
IF NOT EXISTS (SELECT 1 FROM dbo.EMPRESAS WHERE rtn_nit = '08012005445566')
BEGIN
    INSERT INTO dbo.EMPRESAS (nombre_fiscal, rtn_nit, correo_contacto)
    VALUES ('Arena Sport Honduras S. de R.L.', '08012005445566', 'info@arenasport.hn');
END

IF NOT EXISTS (SELECT 1 FROM dbo.EMPRESAS WHERE rtn_nit = '05011998778899')
BEGIN
    INSERT INTO dbo.EMPRESAS (nombre_fiscal, rtn_nit, correo_contacto)
    VALUES ('Inversiones Deportivas del Norte S.A.', '05011998778899', 'contacto@deportesnorte.hn');
END
GO

-- ============================================================================
-- 2. NUEVAS SUCURSALES ASOCIADAS A LAS EMPRESAS
-- ============================================================================
DECLARE @emp_arena INT = (SELECT id_empresa FROM dbo.EMPRESAS WHERE rtn_nit = '08012005445566');
DECLARE @emp_norte INT = (SELECT id_empresa FROM dbo.EMPRESAS WHERE rtn_nit = '05011998778899');
DECLARE @emp_centro INT = (SELECT TOP 1 id_empresa FROM dbo.EMPRESAS ORDER BY id_empresa ASC);

IF NOT EXISTS (SELECT 1 FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Arena Sport Lomas del Guijarro')
BEGIN
    INSERT INTO dbo.SUCURSALES (id_empresa, nombre_sucursal, direccion, telefono, activa)
    VALUES (@emp_arena, 'Arena Sport Lomas del Guijarro', 'Tegucigalpa, Col. Lomas del Guijarro Sur', '2235-4410', 1);
END

IF NOT EXISTS (SELECT 1 FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Arena Sport El Hatillo')
BEGIN
    INSERT INTO dbo.SUCURSALES (id_empresa, nombre_sucursal, direccion, telefono, activa)
    VALUES (@emp_arena, 'Arena Sport El Hatillo', 'Km 6 Carretera a El Hatillo, Tegucigalpa', '2235-4420', 1);
END

IF NOT EXISTS (SELECT 1 FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Complejo Norte San Pedro Sula')
BEGIN
    INSERT INTO dbo.SUCURSALES (id_empresa, nombre_sucursal, direccion, telefono, activa)
    VALUES (@emp_norte, 'Complejo Norte San Pedro Sula', 'San Pedro Sula, Blvd. Mackay', '2556-8800', 1);
END

IF NOT EXISTS (SELECT 1 FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Sede Miramontes')
BEGIN
    INSERT INTO dbo.SUCURSALES (id_empresa, nombre_sucursal, direccion, telefono, activa)
    VALUES (@emp_centro, 'Sede Miramontes', 'Tegucigalpa, Col. Miramontes', '2239-5500', 1);
END
GO

-- ============================================================================
-- 3. CANCHAS Y BLOQUES HORARIOS PARA LAS NUEVAS SUCURSALES
-- ============================================================================
DECLARE @id_fut7 INT = (SELECT TOP 1 id_tipo_cancha FROM dbo.TIPOS_CANCHA WHERE nombre LIKE '%Fútbol%');
DECLARE @id_padel INT = (SELECT TOP 1 id_tipo_cancha FROM dbo.TIPOS_CANCHA WHERE nombre LIKE '%Pádel%');
DECLARE @id_basket INT = (SELECT TOP 1 id_tipo_cancha FROM dbo.TIPOS_CANCHA WHERE nombre LIKE '%Baloncesto%');

IF @id_basket IS NULL
BEGIN
    INSERT INTO dbo.TIPOS_CANCHA (nombre, descripcion)
    VALUES ('Baloncesto', 'Cancha reglamentaria de baloncesto');
    SET @id_basket = SCOPE_IDENTITY();
END

DECLARE @s_lomas INT = (SELECT id_sucursal FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Arena Sport Lomas del Guijarro');
DECLARE @s_hatillo INT = (SELECT id_sucursal FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Arena Sport El Hatillo');
DECLARE @s_sps INT = (SELECT id_sucursal FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Complejo Norte San Pedro Sula');
DECLARE @s_miramontes INT = (SELECT id_sucursal FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Sede Miramontes');

IF NOT EXISTS (SELECT 1 FROM dbo.CANCHAS WHERE nombre = 'Cancha Panorámica Lomas 1' AND id_sucursal = @s_lomas)
    INSERT INTO dbo.CANCHAS (id_sucursal, id_tipo_cancha, nombre, ubicacion_interna, precio_hora, activa)
    VALUES (@s_lomas, @id_padel, 'Cancha Panorámica Lomas 1', 'Terraza Nivel 2', 700.00, 1);

IF NOT EXISTS (SELECT 1 FROM dbo.CANCHAS WHERE nombre = 'Cancha Sintética Hatillo 1' AND id_sucursal = @s_hatillo)
    INSERT INTO dbo.CANCHAS (id_sucursal, id_tipo_cancha, nombre, ubicacion_interna, precio_hora, activa)
    VALUES (@s_hatillo, @id_fut7, 'Cancha Sintética Hatillo 1', 'Bosque Norte', 850.00, 1);

IF NOT EXISTS (SELECT 1 FROM dbo.CANCHAS WHERE nombre = 'Estadio Mackay Fútbol 7' AND id_sucursal = @s_sps)
    INSERT INTO dbo.CANCHAS (id_sucursal, id_tipo_cancha, nombre, ubicacion_interna, precio_hora, activa)
    VALUES (@s_sps, @id_fut7, 'Estadio Mackay Fútbol 7', 'Campo Principal', 900.00, 1);

IF NOT EXISTS (SELECT 1 FROM dbo.CANCHAS WHERE nombre = 'Duela Miramontes Pro' AND id_sucursal = @s_miramontes)
    INSERT INTO dbo.CANCHAS (id_sucursal, id_tipo_cancha, nombre, ubicacion_interna, precio_hora, activa)
    VALUES (@s_miramontes, @id_basket, 'Duela Miramontes Pro', 'Pabellón Central', 650.00, 1);

-- Asignar horarios estándar a todas las sucursales activas que aún no los tengan
DECLARE @bloques TABLE (hora_inicio TIME, hora_fin TIME);
INSERT INTO @bloques (hora_inicio, hora_fin) VALUES
('08:00:00', '09:00:00'),
('09:00:00', '10:00:00'),
('15:00:00', '16:00:00'),
('16:00:00', '17:00:00'),
('17:00:00', '18:00:00'),
('18:00:00', '19:00:00'),
('19:00:00', '20:00:00'),
('20:00:00', '21:00:00');

INSERT INTO dbo.HORARIOS (id_sucursal, hora_inicio, hora_fin)
SELECT s.id_sucursal, b.hora_inicio, b.hora_fin
FROM dbo.SUCURSALES s
CROSS JOIN @bloques b
WHERE s.activa = 1
  AND NOT EXISTS (
      SELECT 1 FROM dbo.HORARIOS h
      WHERE h.id_sucursal = s.id_sucursal
        AND h.hora_inicio = b.hora_inicio
        AND h.hora_fin = b.hora_fin
  );
GO

-- ============================================================================
-- 4. NUEVOS USUARIOS ADMINISTRADORES DE SUCURSALES (Y SUPER ADMIN)
--    Contraseña de prueba para todos: 123456
-- ============================================================================
DECLARE @rol_super INT = (SELECT id_rol FROM dbo.ROLES_ADMIN WHERE nombre_rol = 'Admin General');
DECLARE @rol_sucursal INT = (SELECT id_rol FROM dbo.ROLES_ADMIN WHERE nombre_rol = 'Admin Sucursal');

DECLARE @suc_2 INT = (SELECT id_sucursal FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Sede Anillo Periférico');
DECLARE @suc_lomas INT = (SELECT id_sucursal FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Arena Sport Lomas del Guijarro');
DECLARE @suc_hatillo INT = (SELECT id_sucursal FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Arena Sport El Hatillo');
DECLARE @suc_sps INT = (SELECT id_sucursal FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Complejo Norte San Pedro Sula');
DECLARE @suc_miramontes INT = (SELECT id_sucursal FROM dbo.SUCURSALES WHERE nombre_sucursal = 'Sede Miramontes');

-- Super Admin global (id_sucursal = NULL)
IF NOT EXISTS (SELECT 1 FROM dbo.USUARIOS_ADMINISTRADORES WHERE correo = 'superadmin@reservacancha.com')
    INSERT INTO dbo.USUARIOS_ADMINISTRADORES (id_sucursal, id_rol, primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, correo, password_hash, activo)
    VALUES (NULL, @rol_super, 'Roberto', 'Carlos', 'Aguilar', 'Paz', 'superadmin@reservacancha.com', '123456', 1);

-- Admin Sede Anillo Periférico
IF NOT EXISTS (SELECT 1 FROM dbo.USUARIOS_ADMINISTRADORES WHERE correo = 'admin@sede2.com')
    INSERT INTO dbo.USUARIOS_ADMINISTRADORES (id_sucursal, id_rol, primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, correo, password_hash, activo)
    VALUES (@suc_2, @rol_sucursal, 'Andrea', 'María', 'Castillo', 'Reyes', 'admin@sede2.com', '123456', 1);

-- Admin Arena Sport Lomas
IF NOT EXISTS (SELECT 1 FROM dbo.USUARIOS_ADMINISTRADORES WHERE correo = 'admin.lomas@arenasport.hn')
    INSERT INTO dbo.USUARIOS_ADMINISTRADORES (id_sucursal, id_rol, primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, correo, password_hash, activo)
    VALUES (@suc_lomas, @rol_sucursal, 'Fernando', 'José', 'Salgado', 'Meza', 'admin.lomas@arenasport.hn', '123456', 1);

-- Admin Arena Sport El Hatillo
IF NOT EXISTS (SELECT 1 FROM dbo.USUARIOS_ADMINISTRADORES WHERE correo = 'admin.hatillo@arenasport.hn')
    INSERT INTO dbo.USUARIOS_ADMINISTRADORES (id_sucursal, id_rol, primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, correo, password_hash, activo)
    VALUES (@suc_hatillo, @rol_sucursal, 'Gabriela', 'Lucía', 'Zelaya', 'Ortiz', 'admin.hatillo@arenasport.hn', '123456', 1);

-- Admin Complejo Norte SPS
IF NOT EXISTS (SELECT 1 FROM dbo.USUARIOS_ADMINISTRADORES WHERE correo = 'admin.sps@deportesnorte.hn')
    INSERT INTO dbo.USUARIOS_ADMINISTRADORES (id_sucursal, id_rol, primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, correo, password_hash, activo)
    VALUES (@suc_sps, @rol_sucursal, 'Héctor', 'Manuel', 'Pineda', 'Cruz', 'admin.sps@deportesnorte.hn', '123456', 1);

-- Admin Sede Miramontes
IF NOT EXISTS (SELECT 1 FROM dbo.USUARIOS_ADMINISTRADORES WHERE correo = 'admin.miramontes@complejos.hn')
    INSERT INTO dbo.USUARIOS_ADMINISTRADORES (id_sucursal, id_rol, primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, correo, password_hash, activo)
    VALUES (@suc_miramontes, @rol_sucursal, 'Sofía', 'Elena', 'Barahona', 'Díaz', 'admin.miramontes@complejos.hn', '123456', 1);
GO

-- ============================================================================
-- 5. NUEVOS CLIENTES (3FN: NOMBRES Y APELLIDOS ATÓMICOS)
--    Contraseña de prueba para todos: 123456
-- ============================================================================
IF NOT EXISTS (SELECT 1 FROM dbo.CLIENTES WHERE correo = 'maria.gomez@correo.com')
    INSERT INTO dbo.CLIENTES (primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, telefono, correo, password_hash)
    VALUES ('María', 'Fernanda', 'Gómez', 'Valladares', '9845-1122', 'maria.gomez@correo.com', '123456');

IF NOT EXISTS (SELECT 1 FROM dbo.CLIENTES WHERE correo = 'luis.martinez@correo.com')
    INSERT INTO dbo.CLIENTES (primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, telefono, correo, password_hash)
    VALUES ('Luis', 'Alberto', 'Martínez', 'Cáceres', '9912-3344', 'luis.martinez@correo.com', '123456');

IF NOT EXISTS (SELECT 1 FROM dbo.CLIENTES WHERE correo = 'daniela.rodriguez@correo.com')
    INSERT INTO dbo.CLIENTES (primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, telefono, correo, password_hash)
    VALUES ('Daniela', 'Sofía', 'Rodríguez', 'Flores', '3340-5566', 'daniela.rodriguez@correo.com', '123456');

IF NOT EXISTS (SELECT 1 FROM dbo.CLIENTES WHERE correo = 'kevin.hernandez@correo.com')
    INSERT INTO dbo.CLIENTES (primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, telefono, correo, password_hash)
    VALUES ('Kevin', 'Eduardo', 'Hernández', 'Solórzano', '8876-9900', 'kevin.hernandez@correo.com', '123456');

IF NOT EXISTS (SELECT 1 FROM dbo.CLIENTES WHERE correo = 'paola.mejía@correo.com')
    INSERT INTO dbo.CLIENTES (primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, telefono, correo, password_hash)
    VALUES ('Paola', 'Andrea', 'Mejía', 'Suazo', '9520-7788', 'paola.mejia@correo.com', '123456');

IF NOT EXISTS (SELECT 1 FROM dbo.CLIENTES WHERE correo = 'jorge.ramirez@correo.com')
    INSERT INTO dbo.CLIENTES (primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, telefono, correo, password_hash)
    VALUES ('Jorge', 'Enrique', 'Ramírez', 'Galeano', '9765-4321', 'jorge.ramirez@correo.com', '123456');
GO

-- ============================================================================
-- 6. CONSULTA DE VERIFICACIÓN DE CREDENCIALES Y SEDES
-- ============================================================================
SELECT u.id_usuario,
       CONCAT(u.primer_nombre, ' ', u.primer_apellido) AS administrador,
       u.correo,
       r.nombre_rol AS rol,
       ISNULL(s.nombre_sucursal, 'TODAS LAS SUCURSALES (GLOBAL)') AS sucursal_asignada
FROM dbo.USUARIOS_ADMINISTRADORES u
JOIN dbo.ROLES_ADMIN r ON u.id_rol = r.id_rol
LEFT JOIN dbo.SUCURSALES s ON u.id_sucursal = s.id_sucursal
ORDER BY u.id_usuario;

SELECT id_cliente,
       CONCAT(primer_nombre, ' ', ISNULL(segundo_nombre + ' ', ''), primer_apellido, ' ', ISNULL(segundo_apellido, '')) AS cliente,
       telefono,
       correo,
       password_hash
FROM dbo.CLIENTES
ORDER BY id_cliente;
GO
