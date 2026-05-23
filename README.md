[README_DFS_Bloques.md](https://github.com/user-attachments/files/28183975/README_DFS_Bloques.md)
# Proyecto Sistemas Distribuidos - DFS-Bloques

Sistema de archivos distribuido minimalista basado en bloques, desarrollado para el curso **Arquitecturas de Nube y Sistemas Distribuidos**.

El proyecto implementa un DFS académico compuesto por un **NameNode**, tres **DataNodes** y un **cliente CLI**. Permite subir, dividir, distribuir, replicar, listar, recuperar y eliminar archivos usando comunicación REST sobre HTTP.

---

## Integrantes

- Santiago Restrepo Salazar
- Josue Pino Pino

---

## Descripción general

DFS-Bloques simula un sistema de archivos distribuido por bloques. En lugar de almacenar un archivo completo en un único nodo, el cliente divide el archivo en bloques de tamaño configurable y los distribuye entre varios DataNodes.

El **NameNode** administra los metadatos del sistema:

- Usuarios.
- Directorios.
- Archivos.
- Bloques.
- Orden de los bloques.
- Ubicaciones de réplicas.
- Estado de DataNodes.

Los **DataNodes** almacenan físicamente los bloques. El **cliente CLI** permite interactuar con el sistema mediante comandos como `login`, `put`, `get`, `ls`, `rm`, `mkdir` y `rmdir`.

---

## Arquitectura

La arquitectura combina el modelo **Cliente/Servidor** con el patrón **Maestro-Trabajador**.

```text
Cliente CLI
   │
   │ REST / HTTP - Metadatos, autenticación y control
   ▼
NameNode
   │
   │ Registro y administración de DataNodes
   ▼
DataNodes

Cliente CLI
   │
   │ Transferencia directa de bloques
   ├── DataNode 1
   ├── DataNode 2
   └── DataNode 3
```

### Componentes

| Componente | Descripción |
|---|---|
| Cliente CLI | Ejecuta comandos del usuario y transfiere bloques. |
| NameNode | Administra metadatos, usuarios, archivos, bloques y ubicaciones. |
| DataNode 1 | Almacena bloques físicos. |
| DataNode 2 | Almacena bloques físicos. |
| DataNode 3 | Almacena bloques físicos. |

---

## Tecnologías usadas

- Python 3.11+
- FastAPI
- Uvicorn
- Docker
- Docker Compose
- REST sobre HTTP
- JSON para metadatos
- SHA-256 para validación de integridad

---

## Estructura del proyecto

```text
dfs-bloques/
├── client/
│   ├── cli.py
│   ├── dfs_client.py
│   └── file_utils.py
├── common/
├── datanode/
│   ├── main.py
│   ├── storage.py
│   └── config.py
├── docs/
├── namenode/
│   ├── main.py
│   ├── auth.py
│   ├── metadata_store.py
│   ├── block_allocator.py
│   └── models.py
├── scripts/
│   └── create_sample_file.py
├── tests/
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md
├── docker-compose.yml
└── requirements.txt
```

---

## Puertos de ejecución

| Servicio | Puerto | URL |
|---|---:|---|
| NameNode | 8000 | http://localhost:8000 |
| DataNode 1 | 8001 | http://localhost:8001 |
| DataNode 2 | 8002 | http://localhost:8002 |
| DataNode 3 | 8003 | http://localhost:8003 |

---

## APIs Swagger

Cuando el sistema esté corriendo, se pueden consultar las APIs en:

```text
http://localhost:8000/docs
http://localhost:8001/docs
http://localhost:8002/docs
http://localhost:8003/docs
```

---

## Requisitos previos

Tener instalado:

- Docker Desktop
- Docker Compose
- Python 3.11 o superior
- Git

Verificar Docker:

```powershell
docker ps
```

Si Docker está funcionando, debe aparecer una tabla de contenedores, aunque esté vacía.

---

## Configuración inicial

Clonar el repositorio:

```powershell
git clone https://github.com/josuepinop/Proyecto-Sistemas-Distribuidos-.git
cd Proyecto-Sistemas-Distribuidos-
```

Copiar archivo de variables:

```powershell
copy .env.example .env
```

---

## Ejecución con Docker Compose

Levantar el sistema completo:

```powershell
docker compose up --build
```

Esto inicia:

```text
dfs-namenode
dfs-datanode1
dfs-datanode2
dfs-datanode3
```

En otra terminal, verificar contenedores activos:

```powershell
docker ps
```

---

## Preparar entorno del cliente

En otra terminal de PowerShell:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## Comandos principales

### 1. Verificar estado general

```powershell
python client/cli.py health
```

### 2. Ver DataNodes registrados

```powershell
python client/cli.py datanodes
```

Debe mostrar los nodos:

```text
dn1
dn2
dn3
```

### 3. Login exitoso

```powershell
python client/cli.py login --user santiago --password 1234
```

### 4. Login fallido

```powershell
python client/cli.py login --user santiago --password mala
```

Debe responder con error de credenciales.

---

## Prueba completa de funcionamiento

### 1. Crear archivo de prueba

```powershell
New-Item -ItemType Directory -Force -Path "tests\sample_files"
New-Item -ItemType Directory -Force -Path "downloads"
python scripts/create_sample_file.py --output tests/sample_files/demo.bin --size-mb 3
Get-ChildItem tests\sample_files\demo.bin
```

Esto crea un archivo de aproximadamente 3 MB.

### 2. Subir archivo con particionamiento

```powershell
python client/cli.py put tests/sample_files/demo.bin --name demo.bin --block-size-mb 1
```

Con `--block-size-mb 1`, el archivo de 3 MB se divide en 3 bloques.

Cada bloque se replica en dos DataNodes.

### 3. Ver bloques en los DataNodes

```powershell
Invoke-RestMethod http://localhost:8001/blocks | ConvertTo-Json -Depth 10
Invoke-RestMethod http://localhost:8002/blocks | ConvertTo-Json -Depth 10
Invoke-RestMethod http://localhost:8003/blocks | ConvertTo-Json -Depth 10
```

Esto permite evidenciar la distribución física de bloques entre nodos.

### 4. Listar archivos

```powershell
python client/cli.py ls
```

Debe aparecer `demo.bin` con sus metadatos, bloques, tamaño y ubicaciones.

### 5. Descargar y reconstruir archivo

```powershell
python client/cli.py get demo.bin --output downloads/demo_recuperado.bin
```

El sistema descarga los bloques desde los DataNodes disponibles y reconstruye el archivo.

### 6. Validar integridad con SHA-256

```powershell
Get-FileHash tests\sample_files\demo.bin -Algorithm SHA256
Get-FileHash downloads\demo_recuperado.bin -Algorithm SHA256
```

Los hashes deben coincidir.

---

## Prueba de tolerancia a fallos

### 1. Detener un DataNode

```powershell
docker stop dfs-datanode1
docker ps
```

El contenedor `dfs-datanode1` debe desaparecer de la lista de contenedores activos.

### 2. Recuperar archivo con un DataNode caído

```powershell
python client/cli.py get demo.bin --output downloads/demo_recuperado_fallo.bin
```

El cliente intentará acceder a una réplica en el DataNode detenido, registrará el error y luego usará otra réplica disponible.

### 3. Validar integridad durante la falla

```powershell
Get-FileHash tests\sample_files\demo.bin -Algorithm SHA256
Get-FileHash downloads\demo_recuperado_fallo.bin -Algorithm SHA256
```

Los hashes deben coincidir.

### 4. Revisar logs

```powershell
docker compose logs --tail=100
```

### 5. Volver a levantar el DataNode

```powershell
docker start dfs-datanode1
docker ps
```

---

## Prueba de eliminación

### 1. Eliminar archivo

```powershell
python client/cli.py rm demo.bin
```

### 2. Verificar que desapareció

```powershell
python client/cli.py ls
```

### 3. Intentar descargar archivo eliminado

```powershell
python client/cli.py get demo.bin --output downloads/demo_no_deberia_descargar.bin
```

Debe responder con error controlado:

```text
HTTP 404: Archivo no encontrado
```

---

## Prueba de directorios

### Crear directorio

```powershell
python client/cli.py mkdir documentos
```

### Listar

```powershell
python client/cli.py ls
```

Debe aparecer el directorio `documentos`.

### Eliminar directorio

```powershell
python client/cli.py rmdir documentos
```

### Verificar eliminación

```powershell
python client/cli.py ls
```

---

## Flujo resumido de comandos

```powershell
docker compose up --build
docker ps

python client/cli.py health
python client/cli.py datanodes
python client/cli.py login --user santiago --password 1234

python scripts/create_sample_file.py --output tests/sample_files/demo.bin --size-mb 3
python client/cli.py put tests/sample_files/demo.bin --name demo.bin --block-size-mb 1

python client/cli.py ls
python client/cli.py get demo.bin --output downloads/demo_recuperado.bin

Get-FileHash tests\sample_files\demo.bin -Algorithm SHA256
Get-FileHash downloads\demo_recuperado.bin -Algorithm SHA256

docker stop dfs-datanode1
python client/cli.py get demo.bin --output downloads/demo_recuperado_fallo.bin

Get-FileHash tests\sample_files\demo.bin -Algorithm SHA256
Get-FileHash downloads\demo_recuperado_fallo.bin -Algorithm SHA256

docker start dfs-datanode1

python client/cli.py rm demo.bin
python client/cli.py mkdir documentos
python client/cli.py rmdir documentos
```

---

## Limpieza del entorno

Apagar contenedores:

```powershell
docker compose down
```

Eliminar datos generados localmente:

```powershell
Remove-Item -Recurse -Force "runtime" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "downloads" -ErrorAction SilentlyContinue
Remove-Item -Force ".dfs_session.json" -ErrorAction SilentlyContinue
```

---

## Archivos que no deben subirse

El repositorio ignora archivos generados localmente como:

```text
runtime/
downloads/
.venv/
venv/
.env
.dfs_session.json
__pycache__/
*.pyc
.pytest_cache/
tests/sample_files/*.bin
```

---

## Notas sobre AWS Academy

El sistema fue validado en Docker local como entorno principal de demostración. AWS Academy queda documentado como alternativa de despliegue. En caso de usar AWS, se pueden ejecutar los mismos servicios en una EC2 con Docker Compose o distribuir los DataNodes en varias máquinas ajustando las variables de URL e IP.

---

## Limitaciones

Esta versión es académica y minimalista. No implementa:

- Montaje real como sistema de archivos del sistema operativo.
- Compatibilidad POSIX.
- Alta disponibilidad del NameNode.
- Consenso distribuido.
- Re-replicación automática avanzada.
- Balanceo por capacidad real.
- Cifrado extremo a extremo.
- Permisos avanzados por usuario, grupo o rol.

---

## Conclusión

DFS-Bloques demuestra los conceptos fundamentales de un sistema de archivos distribuido por bloques:

- Separación entre plano de control y plano de datos.
- NameNode para metadatos.
- DataNodes para almacenamiento físico.
- Particionamiento de archivos.
- Replicación de bloques.
- Reconstrucción de archivos.
- Validación de integridad.
- Tolerancia básica ante caída de un DataNode.
- Comunicación REST sobre HTTP.
- Ejecución mediante contenedores Docker.
