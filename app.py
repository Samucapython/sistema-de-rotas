import streamlit as st
import pandas as pd
import requests
import json
import re
import time

# =========================================================================
# CONFIGURAÇÕES IMPORTANTES
# =========================================================================
ID_DO_ARQUIVO_DRIVE = "1bu7iGpJmejm2Trb0zczN-QqT40cMnIh3"
MERCADOPAGO_ACCESS_TOKEN = "APP_USR-6320983636172829-062820-7a079da945b82c5ed49e45f4d5be70dd-169568315"

# 📋 COLE AQUI O LINK COMPLETO QUE VOCÊ COPIOU DO GOOGLE APPS SCRIPT
URL_SALVAR_DRIVE = "https://script.google.com/macros/s/AKfycbxnp5XBcUb3eWgY4gMgVjYsRvdnDVk5PJdtQchlF9a9flfWzAc05Zmgjtn-vtIfblCQsw/exec"

URL_DOWNLOAD = f"https://docs.google.com/uc?export=download&id={ID_DO_ARQUIVO_DRIVE}"

# Funções do Banco de Dados Atualizadas
def carregar_usuarios():
    try:
        resposta = requests.get(URL_DOWNLOAD)
        if resposta.status_code == 200:
            return json.loads(resposta.text)
        else:
            return {}
    except:
        return {}

def salvar_usuarios(dados):
    st.session_state.banco_usuarios = dados
    # Envia os dados novos em tempo real para o Google Drive salvar de verdade
    try:
        requests.post(URL_SALVAR_DRIVE, data=json.dumps(dados))
    except:
        pass

# Inicializar variáveis na memória do navegador do motorista
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.usuario_atual = None
    st.session_state.banco_usuarios = carregar_usuarios()
    st.session_state.pix_criado = None

usuarios = st.session_state.banco_usuarios

# ----------------- TELA DE LOGIN / CADASTRO -----------------
if not st.session_state.logado:
    st.title("🔒 Acesso ao Sistema de Rotas")
    aba1, aba2 = st.tabs(["Fazer Login", "Criar Nova Conta"])
    
    with aba1:
        email = st.text_input("E-mail para Login")
        senha = st.text_input("Senha para Login", type="password")
        if st.button("Entrar"):
            if email in usuarios and usuarios[email]["senha"] == senha:
                st.session_state.logado = True
                st.session_state.usuario_atual = email
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")
                
    with aba2:
        novo_email = st.text_input("Seu melhor E-mail")
        nova_senha = st.text_input("Crie uma Senha", type="password")
        if st.button("Cadastrar Conta"):
            if novo_email in usuarios:
                st.error("Este e-mail já está cadastrado.")
            elif "@" not in novo_email:
                st.error("Por favor, digite um e-mail válido.")
            else:
                usuarios[novo_email] = {"senha": nova_senha, "creditos": 2}
                salvar_usuarios(usuarios)
                st.success("🎉 Conta criada com sucesso! Mude para a aba 'Fazer Login'.")

# ----------------- TELA DO SISTEMA (MOTORISTA LOGADO) -----------------
else:
    email_usuario = st.session_state.usuario_atual
    creditos_atuais = usuarios[email_usuario]["creditos"]
    
    st.title("🚗 Corretor de Rotas SPX TN")
    st.write(f"Motorista: **{email_usuario}**")
    st.metric(label="Seus Créditos Disponíveis", value=f"🪙 {creditos_atuais}")

    if st.button("🚪 Sair da Conta"):
        st.session_state.logado = False
        st.session_state.usuario_atual = None
        st.session_state.pix_criado = None
        st.rerun()

    st.markdown("---")

    # SE O MOTORISTA NÃO TEM CRÉDITOS
    if creditos_atuais <= 0:
        st.warning("⚠️ Você não possui créditos para processar novas rotas.")
        st.subheader("Adquira 1 Crédito por R$ 12,00 via PIX")
        
        if st.button("🏷️ Gerar PIX de R$ 12,00"):
            url_mp = "https://api.mercadopago.com/v1/payments"
            
            # Gerando chave única de idempotência com base no e-mail e tempo atual
            chave_unica = f"{email_usuario}-{int(time.time())}"
            
            headers = {
                "Authorization": f"Bearer {MERCADOPAGO_ACCESS_TOKEN}",
                "Content-Type": "application/json",
                "X-Idempotency-Key": chave_unica
            }
            
            # Tratamento para garantir formato de e-mail válido aceito pelo Mercado Pago
            email_valido_mp = email_usuario if "@" in email_usuario else f"{email_usuario}@email.com"
            
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
                    # Exibe o motivo exato retornado pela API do Mercado Pago se houver falha
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
                        checagem = requests.get(url_checa, headers=headers).json()
                        if checagem.get("status") == "approved":
                            pago = True
                            break
                        time.sleep(1)
                    
                    if pago:
                        usuarios[email_usuario]["creditos"] += 1
                        salvar_usuarios(usuarios)
                        st.session_state.pix_criado = None
                        st.success("🎉 Pagamento aprovado! 1 Crédito adicionado com sucesso.")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("Ainda não recebemos a confirmação. Se você já pagou, aguarde 10 segundos e clique novamente.")

    # SE O MOTORISTA TEM CRÉDITOS
    else:
        # 1. Aqui você mudou certo! Aceita o arquivo .xlsx do Excel
        uploaded_file = st.file_uploader("Selecione o arquivo baixado do SPX TN (.xlsx)", type=["xlsx"])
        
        if uploaded_file is not None:
            # CORREÇÃO 1: O comando correto do Python é read_excel
            df = pd.read_excel(uploaded_file, keep_default_na=False)
            
            if "Sequence" in df.columns:
                df = df[df['Sequence'] != '-']
            
            if "Destination Address" in df.columns:
                df["Destination Address"] = df["Destination Address"].astype(str).str.replace(r'[\r\n]+', ' ', regex=True)
                
                def limpar_ruas(texto):
                    texto = re.sub(r'^(Rua|R\.|R)\b', 'Rua', texto, flags=re.IGNORECASE)
                    texto = re.sub(r'^(Av\.|Av)\b', 'Avenida', texto, flags=re.IGNORECASE)
                    texto = re.sub(r'^(Est\.|Est)\b', 'Estrada', texto, flags=re.IGNORECASE)
                    return texto
                df["Destination Address"] = df["Destination Address"].apply(limpar_ruas)
                
                df['Chave_Endereco'] = df['Destination Address'].astype(str) + "_" + df['Latitude'].astype(str) + "_" + df['Longitude'].astype(str)
                
                nova_parada = 1
                lista_novas_paradas = []
                enderecos_vistos = {}
                
                for id_endereco in df['Chave_Endereco']:
                    if id_endereco not in enderecos_vistos:
                        enderecos_vistos[id_endereco] = nova_parada
                        nova_parada += 1
                    lista_novas_paradas.append(enderecos_vistos[id_endereco])
                
                df['Stop'] = lista_novas_paradas
                df = df.drop(columns=['Chave_Endereco'])
            
            st.success("✨ Seu arquivo foi corrigido e as paradas foram individualizadas por casa!")
            
            # CORREÇÃO 2: Mantemos a saída em .csv estruturado para o Circuit aceitar perfeito e sem erros de formatação
            csv_corrigido = df.to_csv(index=False).encode('utf-8')
            
            if st.download_button(
                label="📥 Baixar Arquivo Corrigido (Gasta 1 crédito)",
                data=csv_corrigido,
                file_name="rota_corrigida.csv",
                mime="text/csv"
            ):
                usuarios[email_usuario]["creditos"] -= 1
                salvar_usuarios(usuarios)
                st.rerun()