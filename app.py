import streamlit as st
import pandas as pd
import requests
import json
import re
import time
from urllib.parse import quote

# =========================================================================
# CONFIGURAÇÕES IMPORTANTES
# =========================================================================
ID_DO_ARQUIVO_DRIVE = "1bu7iGpJmejm2Trb0zczN-QqT40cMnIh3"
MERCADOPAGO_ACCESS_TOKEN = "APP_USR-6320983636172829-062820-7a079da945b82c5ed49e45f4d5be70dd-169568315"
URL_SALVAR_DRIVE = "https://script.google.com/macros/s/AKfycbxnp5XBcUb3eWgY4gMgVjYsRvdnDVk5PJdtQchlF9a9flfWzAc05Zmgjtn-vtIfblCQsw/exec"

URL_DOWNLOAD = f"https://docs.google.com/uc?export=download&id={ID_DO_ARQUIVO_DRIVE}"

def carregar_banco():
    try:
        url_sem_cache = f"{URL_DOWNLOAD}&nocache={int(time.time())}"
        resposta = requests.get(url_sem_cache)
        if resposta.status_code == 200:
            dados = json.loads(resposta.text)
            if "usuarios" not in dados:
                dados = {"usuarios": dados, "motoristas_bloqueados": []}
            return dados
        else:
            return {"usuarios": {}, "motoristas_bloqueados": []}
    except:
        return {"usuarios": {}, "motoristas_bloqueados": []}

def salvar_banco(dados):
    st.session_state.banco_completo = dados
    try:
        requests.post(URL_SALVAR_DRIVE, data=json.dumps(dados))
    except:
        pass

if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.usuario_atual = None
    st.session_state.banco_completo = carregar_banco()
    st.session_state.pix_criado = None

banco = st.session_state.banco_completo
usuarios = banco["usuarios"]
motoristas_bloqueados = banco["motoristas_bloqueados"]

# --- FUNÇÃO INTELIGENTE DE CONSULTA AO MAPA (OPENSTREETMAP) ---
def consultar_coordenadas_internet(endereco_texto, cidade="São Paulo"):
    """Consulta a internet para obter a localização física real do endereço sem complementos"""
    try:
        # Pega de forma limpa apenas até o primeiro número após a vírgula (Rua X, 123)
        busca_padrao = re.search(r'^([^,]+,\s*\d+)', endereco_texto)
        if busca_padrao:
            query_busca = f"{busca_padrao.group(1)}, {cidade}, Brazil"
        else:
            query_busca = f"{endereco_texto}, {cidade}, Brazil"
            
        url = f"https://nominatim.openstreetmap.org/search?q={quote(query_busca)}&format=json&limit=1"
        # User-Agent obrigatório exigido pelos termos da API do OpenStreetMap para evitar bloqueios
        headers = {"User-Agent": "CorretorRotasSPXTN/2.0 (suporte_sistema@provedor.com)"}
        
        resposta = requests.get(url, headers=headers, timeout=3)
        if resposta.status_code == 200 and len(resposta.json()) > 0:
            dados = response_data = resposta.json()[0]
            # Arredonda para 4 casas decimais para unificar condomínios e prédios de entrada dupla
            lat = round(float(dados["lat"]), 4)
            lon = round(float(dados["lon"]), 4)
            return f"{lat}_{lon}"
    except:
        pass
    return None

# ----------------- TELA DE LOGIN / CADASTRO -----------------
if not st.session_state.logado:
    st.title("🔒 Acesso ao Sistema de Rotas")
    aba1, aba2 = st.tabs(["Fazer Login", "Criar Nova Conta"])
    
    with aba1:
        usuario_input = st.text_input("E-mail ou Telefone (com DDD)")
        senha = st.text_input("Senha para Login", type="password")
        if st.button("Entrar"):
            usuario_limpo = usuario_input.strip()
            if usuario_limpo in usuarios and usuarios[usuario_limpo]["senha"] == senha:
                st.session_state.logado = True
                st.session_state.usuario_atual = usuario_limpo
                st.rerun()
            else:
                st.error("Dados de acesso incorretos.")
                
    with aba2:
        opcao_cadastro = st.radio("Como deseja se cadastrar?", ["Usar Telefone/WhatsApp", "Usar E-mail"])
        
        if opcao_cadastro == "Usar Telefone/WhatsApp":
            novo_usuario = st.text_input("Digite seu Telefone com DDD (ex: 11999998888)")
        else:
            novo_usuario = st.text_input("Digite seu melhor E-mail")
            
        nova_senha = st.text_input("Crie uma Senha", type="password")
        
        if st.button("Cadastrar Conta"):
            usuario_final = novo_usuario.strip()
            
            if not usuario_final or len(nova_senha) < 3:
                st.error("Por favor, preencha os dados corretamente.")
            elif usuario_final in usuarios:
                st.error("Este e-mail ou telefone já está cadastrado.")
            elif opcao_cadastro == "Usar E-mail" and "@" not in usuario_final:
                st.error("Por favor, digite um e-mail válido.")
            elif opcao_cadastro == "Usar Telefone/WhatsApp" and not usuario_final.isdigit():
                st.error("Por favor, digite apenas números no campo de telefone.")
            else:
                usuarios[usuario_final] = {"senha": nova_senha, "creditos": 2, "total_pago": 0}
                banco["usuarios"] = usuarios
                salvar_banco(banco)
                st.success("🎉 Conta criada com sucesso! Vá para a aba 'Fazer Login'.")

# ----------------- TELA DO SISTEMA (MOTORISTA LOGADO) -----------------
else:
    email_usuario = st.session_state.usuario_atual
    creditos_atuais = usuarios[email_usuario]["creditos"]
    total_pago = usuarios[email_usuario].get("total_pago", 0)
    
    st.title("🚗 Corretor de Rotas SPX TN")
    st.write(f"Conectado como: **{email_usuario}**")
    st.metric(label="Suas Rotas Disponíveis", value=f"🪙 {creditos_atuais}")

    if st.button("🚪 Sair da Conta"):
        st.session_state.logado = False
        st.session_state.usuario_atual = None
        st.session_state.pix_criado = None
        st.rerun()

    st.markdown("---")

    # SE O MOTORISTA NÃO TEM CRÉDITOS
    if creditos_atuais <= 0:
        st.warning("⚠️ Você não possui rotas disponíveis para processar novos arquivos.")
        st.subheader("Adquira 1 Rota por R$ 12,00 via PIX")
        
        if st.button("🏷️ Gerar PIX de R$ 12,00"):
            url_mp = "https://api.mercadopago.com/v1/payments"
            chave_unica = f"user-{int(time.time())}"
            
            headers = {
                "Authorization": f"Bearer {MERCADOPAGO_ACCESS_TOKEN}",
                "Content-Type": "application/json",
                "X-Idempotency-Key": chave_unica
            }
            
            email_valido_mp = email_usuario if "@" in email_usuario else f"{email_usuario}@telefone.com"
            
            dados_pagamento = {
                "transaction_amount": 12.00,
                "description": f"Credito Rota - {email_usuario}",
                "payment_method_id": "pix",
                "payer": {
                    "email": email_valido_mp,
                    "first_name": "Motorista",
                    "last_name": "SPX"
                }
            }
            
            with st.spinner("Criando PIX no Mercado Pago..."):
                resposta = requests.post(url_mp, headers=headers, json=dados_pagamento)
                if resposta.status_code == 201:
                    dados_resposta = resposta.json()
                    st.session_state.pix_criado = {
                        "id": dados_resposta["id"],
                        "copia_e_cola": dados_resposta["point_of_interaction"]["transaction_data"]["qr_code"]
                    }
                else:
                    st.error(f"Erro ao gerar PIX. Resposta do banco: {resposta.text}")

        if st.session_state.pix_criado:
            st.info("👇 Copie o código abaixo e pague no aplicativo do seu banco:")
            st.code(st.session_state.pix_criado["copia_e_cola"], language="text")
            
            if st.button("🔄 Já paguei! Verificar aprovação"):
                id_pagamento = st.session_state.pix_criado["id"]
                url_checa = f"https://api.mercadopago.com/v1/payments/{id_pagamento}"
                headers = {"Authorization": f"Bearer {MERCADOPAGO_ACCESS_TOKEN}"}
                
                with st.spinner("Buscando confirmação do seu banco..."):
                    pago = False
                    for _ in range(5):
                        try:
                            checagem = requests.get(url_checa, headers=headers).json()
                            if checagem.get("status") == "approved":
                                pago = True
                                break
                        except:
                            pass
                        time.sleep(1)
                    
                    if pago:
                        usuarios[email_usuario]["creditos"] += 1
                        usuarios[email_usuario]["total_pago"] = total_pago + 12.00
                        banco["usuarios"] = usuarios
                        salvar_banco(banco)
                        st.session_state.pix_criado = None
                        st.success("🎉 Pagamento aprovado! 1 Rota adicionada com sucesso.")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("Ainda não recebemos a confirmação. Se você já pagou, aguarde 10 segundos e clique novamente.")

    # SE O MOTORISTA TEM CRÉDITOS
    else:
        uploaded_file = st.file_uploader("Selecione o arquivo baixado do SPX TN (.xlsx)", type=["xlsx"])
        
        if uploaded_file is not None:
            nome_do_arquivo = uploaded_file.name
            
            nome_limpo = re.sub(r'^[\d\-_\s]+', '', nome_do_arquivo)
            nome_limpo = re.sub(r'\s*\([^)]*\)', '', nome_limpo)
            nome_motorista = nome_limpo.replace(".xlsx", "").strip().upper()
            
            if total_pago <= 0 and creditos_atuais <= 0 and nome_motorista in motoristas_bloqueados:
                st.error(f"❌ Erro de Validação: O motorista '{nome_motorista}' já utilizou o bônus de 2 rotas gratuitas em outra conta. Para processar este arquivo, utilize sua conta original ou adquira rotas pagas via PIX.")
            else:
                df = pd.read_excel(uploaded_file, keep_default_na=False)
                
                if "Sequence" in df.columns:
                    df = df[df['Sequence'] != '-']
                
                if "Destination Address" in df.columns:
                    df["Destination Address"] = df["Destination Address"].astype(str).str.replace(r'[\r\n]+', ' ', regex=True)
                    
                    def limpar_ruas(texto):
                        texto = re.sub(r'^(Rua|R\.|R)\b', 'Rua', texto, flags=re.IGNORECASE)
                        texto = re.sub(r'^(Av\.|Av)\b', 'Avenida', texto, flags=re.IGNORECASE)
                        texto = re.sub(r'^(Est\.|Est)\b', 'Estrada', texto, flags=re.IGNORECASE)
                        texto = re.sub(r'^(Tv\.|Tv|Travessa)\b', 'Travessa', texto, flags=re.IGNORECASE)
                        return texto
                    df["Destination Address"] = df["Destination Address"].apply(limpar_ruas)
                    
                    # Detecta a cidade dominante da planilha de forma dinâmica
                    cidade_detectada = "São Paulo"
                    if "City" in df.columns and len(df["City"]) > 0:
                        cidade_detectada = df["City"].iloc[0]
                    
                    # --- PROCESSAMENTO INTELIGENTE DA INTERNET ---
                    st.info("🗺️ **Inteligência Geográfica:** Consultando mapa digital em tempo real para unificar condomínios e numerações duplas...")
                    barra_progresso = st.progress(0)
                    status_texto = st.empty()
                    
                    enderecos_unicos = df["Destination Address"].unique()
                    total_enderecos = len(enderecos_unicos)
                    mapa_coordenadas_reais = {}
                    
                    for idx, endereco in enumerate(enderecos_unicos):
                        status_texto.write(f"Analisando local {idx+1} de {total_enderecos}...")
                        barra_progresso.progress((idx + 1) / total_enderecos)
                        
                        # Consulta a localização real no OpenStreetMap
                        chave_fisica = consultar_coordenadas_internet(endereco, cidade=cidade_detectada)
                        
                        # [REDE DE SEGURANÇA] Se a internet falhar ou não achar, usa a coordenada da SPX corrigida
                        if not chave_fisica:
                            linha_original = df[df["Destination Address"] == endereco].iloc[0]
                            try:
                                lat_seg = str(round(float(linha_original['Latitude']), 4))
                                lon_seg = str(round(float(linha_original['Longitude']), 4))
                                chave_fisica = f"{lat_seg}_{lon_seg}"
                            except:
                                chave_fisica = "LOCAL_SEM_MAPA"
                                
                        mapa_coordenadas_reais[endereco] = chave_fisica
                        time.sleep(1) # Intervalo respeitoso exigido pelo OpenStreetMap
                        
                    barra_progresso.empty()
                    status_texto.empty()
                    
                    # Associa as chaves geográficas encontradas de volta ao DataFrame principal
                    df['Chave_Fisica_Real'] = df["Destination Address"].map(mapa_coordenadas_reais)
                    
                    # --- ATRIBUIÇÃO SEQUENCIAL DOS STOPS ---
                    nova_parada = 1
                    lista_novas_paradas = []
                    locais_vistos = {}
                    
                    for id_fisico in df['Chave_Fisica_Real']:
                        if id_fisico not in locais_vistos:
                            locais_vistos[id_fisico] = nova_parada
                            nova_parada += 1
                        lista_novas_paradas.append(locais_vistos[id_fisico])
                    
                    df['Stop'] = lista_novas_paradas
                    
                    st.success("✨ Seu arquivo foi corrigido e as paradas foram agrupadas geograficamente!")
                    
                    # --- BLOCO DE ALERTA DE GRANDES VOLUMES NO MESMO LOCAL ---
                    st.subheader("📦 Alerta de Grandes Volumes (Mesmo Local):")
                    
                    def extrair_texto_exibicao(texto):
                        padrao = r'^([^,]+,\s*\d+)'
                        busca = re.search(padrao, texto)
                        return busca.group(1).strip().upper() if busca else texto.strip().upper()
                        
                    df['End_Tela'] = df["Destination Address"].apply(extrair_texto_exibicao)
                    
                    contagem = df.groupby(['Chave_Fisica_Real', 'Stop']).agg({'End_Tela': 'first', 'Sequence': 'count'}).reset_index()
                    contagem.rename(columns={'Sequence': 'Qtd'}, inplace=True)
                    multiplos = contagem[contagem['Qtd'] > 1].sort_values(by='Qtd', ascending=False)
                    
                    if not multiplos.empty:
                        for _, row in multiplos.iterrows():
                            st.info(f"📍 **Stop {row['Stop']}** — {row['End_Tela']}: possui **{row['Qtd']} pacotes** unificados nesta mesma parada física!")
                    else:
                        st.write("Todas as entregas de hoje são em locais individuais.")
                    
                    # Remove as colunas de controle interno para entregar o arquivo limpo
                    df = df.drop(columns=['Chave_Fisica_Real', 'End_Tela'])
                
                csv_corrigido = df.to_csv(index=False).encode('utf-8')
                
                if st.download_button(
                    label="📥 Baixar Arquivo Corrigido (Gasta 1 Rota)",
                    data=csv_corrigido,
                    file_name="rota_corrigida.csv",
                    mime="text/csv"
                ):
                    st.success(f"🎉 Rota liberada com sucesso! Boa viagem e ótimas entregas, {nome_motorista}! 🚀")
                    
                    if total_pago <= 0 and nome_motorista not in motoristas_bloqueados:
                        motoristas_bloqueados.append(nome_motorista)
                        banco["motoristas_bloqueados"] = motoristas_bloqueados
                    
                    usuarios[email_usuario]["creditos"] -= 1
                    banco["usuarios"] = usuarios
                    
                    salvar_banco(banco)
                    time.sleep(2.5) 
                    st.rerun()