#!/bin/bash

# Script para generar archivos de Docker a partir de plantillas

# Verificar que se ha pasado el nombre del proyecto
if [ -z "$1" ]; then
  echo "Uso: $0 <nombre_del_proyecto>"
  exit 1
fi

PROJECT_NAME=$1
PROJECT_CONFIG_FILE="projects/$PROJECT_NAME/config.yaml"
GENERATED_DIR="generated/$PROJECT_NAME"

# Verificar que el archivo de configuración del proyecto existe
if [ ! -f "$PROJECT_CONFIG_FILE" ]; then
  echo "Error: El archivo de configuración '$PROJECT_CONFIG_FILE' no existe."
  exit 1
fi

# Crear directorio de salida
mkdir -p "$GENERATED_DIR"

# Leer variables desde config.yaml (esto es una simplificación, un parser de YAML sería mejor)
REPO_URL=$(grep 'repo_url:' "$PROJECT_CONFIG_FILE" | awk '{print $2}')
INSTALL_COMMAND=$(grep 'install_command:' "$PROJECT_CONFIG_FILE" | awk -F': ' '{print $2}' | tr -d '"')
TEST_COMMAND=$(grep 'test_command:' "$PROJECT_CONFIG_FILE" | awk -F': ' '{print $2}' | tr -d '"')
EXPOSE_PORT=$(grep 'expose_port:' "$PROJECT_CONFIG_FILE" | awk '{print $2}')

# Copiar y procesar la plantilla de Dockerfile
sed -e "s/{{PROJECT_NAME}}/$PROJECT_NAME/g" \
    -e "s|{{REPO_URL}}|$REPO_URL|g" \
    -e "s/{{INSTALL_COMMAND}}/$INSTALL_COMMAND/g" \
    -e "s/{{TEST_COMMAND}}/$TEST_COMMAND/g" \
    -e "s/{{EXPOSE_PORT}}/$EXPOSE_PORT/g" \
    "templates/Dockerfile.template" > "$GENERATED_DIR/Dockerfile"

# Copiar y procesar la plantilla de docker-compose
sed -e "s/{{PROJECT_NAME}}/$PROJECT_NAME/g" \
    -e "s/{{EXPOSE_PORT}}/$EXPOSE_PORT/g" \
    "templates/docker-compose.yml.template" > "$GENERATED_DIR/docker-compose.yml"

echo "Archivos Docker generados en '$GENERATED_DIR'"