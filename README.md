# ZapDin PDV

Executável local que roda na máquina do cliente (caixa/PDV) e serve como ponte entre o ERP e o ZapDin App no servidor.

## Arquitetura

```
ERP (local) ──► ZapDin PDV (localhost:4600) ──► ZapDin App (servidor)
```

## Instalação Rápida (Windows)

1. Copie a pasta `ZapDinPDV` para a máquina do cliente
2. Renomeie `.env.example` para `.env`
3. Edite o `.env`:
```env
ZAPDIN_URL=https://seu-servidor.com.br
ZAPDIN_USERNAME=usuario_do_app
ZAPDIN_PASSWORD=senha123
PDV_PORT=4600
PDV_API_KEY=chave-secreta-do-pdv
PDV_NOME=Caixa 01
```
4. Execute `ZapDinPDV.exe`

## API para o ERP

Base URL: `http://localhost:4600`  
Header obrigatório: `X-PDV-Key: {PDV_API_KEY}`

### Verificar Status
```http
GET /status
```
```json
{
  "ok": true,
  "pdv": "Caixa 01",
  "sessoes_conectadas": 1,
  "sessoes": [{"id": "abc123", "nome": "Principal", "status": "connected"}]
}
```

### Listar Sessões WhatsApp
```http
GET /sessoes
```

### Obter QR Code WhatsApp
```http
GET /qr/{sessao_id}
```
```json
{"ok": true, "qr": "data:image/png;base64,..."}
```

### Enviar Mensagem de Texto
```http
POST /enviar/texto
Content-Type: application/json
X-PDV-Key: minha-chave

{
  "phone": "44999990000",
  "message": "Olá, seu pedido foi confirmado!",
  "sessao_id": null
}
```

### Enviar Arquivo (Base64)
```http
POST /enviar/arquivo
Content-Type: application/json
X-PDV-Key: minha-chave

{
  "phone": "44999990000",
  "filename": "nota_fiscal.pdf",
  "file_base64": "JVBERi0xLjQ...",
  "caption": "Sua nota fiscal"
}
```

### Enviar Arquivo via URL
```http
POST /enviar/arquivo-url
Content-Type: application/json
X-PDV-Key: minha-chave

{
  "phone": "44999990000",
  "url": "https://meu-erp.com/nf/123.pdf",
  "filename": "nf_123.pdf",
  "caption": "Nota Fiscal #123"
}
```

### QR de Configuração (para o ERP escanear)
```http
GET /setup/qr
```
Abre uma página HTML com QR code contendo os dados de conexão do PDV. O ERP escaneia uma vez para configurar automaticamente.

## Documentação Interativa

Acesse `http://localhost:4600/docs` enquanto o PDV estiver rodando.

## Build do Executável

```bash
# Instala PyInstaller
pip install pyinstaller

# Gera o .exe
python pdv/build_exe.py
```

O executável fica em `pdv/dist/ZapDinPDV/`.
