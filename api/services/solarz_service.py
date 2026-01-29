import json
import logging
from datetime import datetime
import unicodedata
from sqlalchemy import or_

from ..models import db, Usina, Cliente, ClienteAcessoSolarz

def normalize_string(s):
    """Remove acentos e converte para minúsculas para comparação."""
    if not s:
        return ""
    if not isinstance(s, str):
        return str(s)
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn').lower().strip()

def get_or_create_placeholder_client():
    """Busca ou cria o cliente padrão para usinas importadas."""
    PLACEHOLDER_NAME = "SolarZ - Cliente não informado"
    
    cliente = Cliente.query.filter_by(nome=PLACEHOLDER_NAME).first()
    if not cliente:
        cliente = Cliente(nome=PLACEHOLDER_NAME)
        db.session.add(cliente)
        db.session.flush() # Garante ID
        logging.info(f"Cliente placeholder criado: ID {cliente.id_cliente}")
        
    return cliente

def processar_sincronizacao_solarz(lista_raw):
    """
    Processa uma lista de usinas cruas vindas da SolarZ.
    Retorna resumo das operações.
    """
    stats = {"total_lidas": len(lista_raw), "novas": 0, "atualizadas": 0, "erros": 0}
    
    # Garante que o cliente placeholder existe antes de começar
    placeholder_client = get_or_create_placeholder_client()
    placeholder_client_id = placeholder_client.id_cliente
    
    for raw in lista_raw:
        try:
            resultado = upsert_usina_solarz(raw, placeholder_client_id)
            if resultado == 'nova':
                stats['novas'] += 1
            elif resultado == 'atualizada':
                stats['atualizadas'] += 1
        except Exception as e:
            logging.error(f"Erro ao sincronizar usina SolarZ {raw.get('name', '???')}: {e}")
            stats['erros'] += 1
            
    # Commit em lote ao final (ou poderia ser a cada item se preferir segurança extrema)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro fatal no commit da sincronização: {e}")
        raise e
        
    return stats

def upsert_usina_solarz(raw, placeholder_client_id):
    """
    Aplica a regra de conciliação (Matching) e Upsert Conservador.
    """
    
    # Extração segura dos dados raw
    s_uuid = raw.get('uuid')
    s_id = raw.get('id')
    raw_name = raw.get('name')
    
    endereco = raw.get('endereco') or {}
    
    # Dados transformados
    nome_norm = normalize_string(raw_name)
    cidade_norm = normalize_string(endereco.get('cidade'))
    estado_norm = normalize_string(endereco.get('siglaEstado'))
    
    # --- 1. TENTATIVA DE MATCH ---
    usina = None
    
    # A. Match por UUID (Definitivo)
    if s_uuid:
        usina = Usina.query.filter_by(solarz_uuid=s_uuid).first()
        
    # B. Match por ID (Definitivo)
    if not usina and s_id:
        usina = Usina.query.filter_by(solarz_id=s_id).first()
        
    # C. Fallback: Conciliação Semântica (Apenas se não achou pelos IDs)
    fallback_used = False
    if not usina and raw_name:
        # Busca potenciais candidatos por nome parecido ou exato
        # Como normalização no banco pode ser complexa, buscamos pelo nome exato ou ILIKE primeiro
        # Aqui, vamos iterar filtrando se o banco não for muito grande, ou Query ILIKE
        # Vamos tentar filtro exato primeiro para performance
        candidates = Usina.query.filter(Usina.nome_usina.ilike(f"%{raw_name}%")).all()
        
        for cand in candidates:
            # Refina a busca com normalização python side
            c_nome = normalize_string(cand.nome_usina)
            c_cidade = normalize_string(cand.cidade)
            c_estado = normalize_string(cand.estado)
            
            # Regra: Nome E (Cidade OU Estado) devem bater
            # (Adicionamos Cidade/Estado para evitar "Usina Norte" em 2 estados diferentes serem mergeadas)
            if c_nome == nome_norm:
                if (cidade_norm and c_cidade == cidade_norm) or \
                   (estado_norm and c_estado == estado_norm):
                    usina = cand
                    fallback_used = True
                    break

    # --- 2. AÇÃO (CRIAR ou ATUALIZAR) ---
    is_new = False
    
    if not usina:
        # CRIAR NOVA
        usina = Usina(
            id_cliente=placeholder_client_id, # Placeholder obrigatório
            nome_usina=raw_name or "Usina SolarZ Sem Nome"
        )
        db.session.add(usina)
        is_new = True
    else:
        # EXISTENTE
        # Se veio do fallback, NÃO alteramos o cliente.
        # Se veio do UUID/ID, já confiamos no vínculo, também não alteramos cliente.
        pass

    # --- 3. ATUALIZAÇÃO DE CAMPOS (CONSERVADOR) ---
    # Só atualiza se o campo no banco estiver vazio ou nulo
    
    def update_if_empty(obj, attr, value):
        current_val = getattr(obj, attr)
        # Se current_val for None ou string vazia, E value tiver valor
        if (current_val is None or current_val == "") and (value is not None and value != ""):
            setattr(obj, attr, str(value))
            
    # Atualiza endereço se vazio no banco
    update_if_empty(usina, 'latitude', endereco.get('latitude'))
    update_if_empty(usina, 'longitude', endereco.get('longitude'))
    update_if_empty(usina, 'logradouro', endereco.get('logradouro'))
    update_if_empty(usina, 'bairro', endereco.get('bairro'))
    update_if_empty(usina, 'cidade', endereco.get('cidade'))
    update_if_empty(usina, 'estado', endereco.get('siglaEstado'))
    update_if_empty(usina, 'cep', endereco.get('cep'))
    # pais não vem no JSON de exemplo, ignorar ou padrão Brasil
    
    # --- NOVO: Tags ---
    raw_tags = raw.get('tags')
    tags_str = ""
    if raw_tags and isinstance(raw_tags, list):
        processed = []
        for t in raw_tags:
            if isinstance(t, str): 
                processed.append(t)
            elif isinstance(t, dict): 
                # Tenta pegar campos comuns de tag
                txt = t.get('descricao') or t.get('name') or t.get('label') or ''
                processed.append(txt)
        tags_str = ", ".join(filter(None, processed))
    
    # Atualiza tags sempre que vierem, pois tags mudam com frequencia
    if raw_tags is not None:
        usina.tags = tags_str
    
    # --- 4. VÍNCULO TÉCNICO ---
    # Sempre atualiza os IDs SolarZ se eles vierem
    if s_id: usina.solarz_id = s_id
    if s_uuid: usina.solarz_uuid = s_uuid
    
    # --- 5. VÍNCULO CLIENTE (SOLICITAÇÃO) ---
    usuario_id = raw.get('usuarioId')
    if usuario_id:
        # A. Persiste o ID cru na coluna nova (para relatórios SQL puros)
        usina.cliente_id_solarz = int(usuario_id)
        
        # B. Tenta atualizar a FK real do sistema para integração nativa
        # CORREÇÃO: Respeita vínculo manual existente.
        # Só atualiza a FK se a usina estiver vinculada ao cliente placeholder.
        if usina.id_cliente == placeholder_client_id:
            cliente_real = Cliente.query.filter_by(solarz_id=usuario_id).first()
            if cliente_real:
                usina.id_cliente = cliente_real.id_cliente
    
    # --- 6. PAYLOAD CLEANING & SAVE ---
    # Remove campos efêmeros (URLs assinadas) para evitar updates falsos
    raw_clean = raw.copy()
    keys_to_remove = [k for k in raw_clean.keys() if 'avatarPath' in k or 'capaPath' in k]
    for k in keys_to_remove:
        raw_clean.pop(k, None)

    usina.solarz_payload = json.dumps(raw_clean)
    usina.solarz_payload_updated_at = datetime.utcnow()
    usina.solarz_last_sync_at = datetime.utcnow()
    
    return 'nova' if is_new else 'atualizada'

def processar_sincronizacao_clientes(lista_raw):
    """
    Processa lista de clientes vindos da SolarZ.
    """
    stats = {"total_lidas": len(lista_raw), "novas": 0, "atualizadas": 0, "erros": 0}
    
    for raw in lista_raw:
        try:
            resultado = upsert_cliente_solarz(raw)
            if resultado == 'nova':
                stats['novas'] += 1
            elif resultado == 'atualizada':
                stats['atualizadas'] += 1
        except Exception as e:
            logging.error(f"Erro ao sincronizar cliente SolarZ {raw.get('nome', '???')}: {e}")
            stats['erros'] += 1
            
    try:
        db.session.commit()
        
        # APÓS COMMIT: Processa Analytics de Acesso
        analytics_stats = registrar_acessos_solarz()
        logging.info(f"Analytics Acessos: {analytics_stats}")
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro fatal no commit de clientes: {e}")
        raise e
        
    return stats

def upsert_cliente_solarz(raw):
    """
    Upsert de Cliente via SolarZ.
    Match: UUID > ID > Documento.
    """
    s_uuid = raw.get('uuid')
    s_id = raw.get('id')
    raw_name = raw.get('nome')
    raw_doc = raw.get('documento')
    raw_email = raw.get('email')
    
    # --- 1. Match ---
    cliente = None
    if s_uuid:
        cliente = Cliente.query.filter_by(solarz_uuid=s_uuid).first()
    if not cliente and s_id:
        cliente = Cliente.query.filter_by(solarz_id=s_id).first()
    if not cliente and raw_doc:
        # Tenta match exato por documento (CPF/CNPJ) se fornecido
        # Pela segurança, se documento existir em outro cliente que não tenha solarz_id, assumimos match
        cliente = Cliente.query.filter_by(documento=raw_doc).first()
        
    # --- 2. Create/Get ---
    is_new = False
    if not cliente:
        # Se não achou, cria
        cliente = Cliente(nome=raw_name or "Cliente SolarZ Importado")
        db.session.add(cliente)
        is_new = True
        
    # --- 3. Updates ---
    
    # Helper local (ou poderia mover para escopo global do módulo)
    def update_if_empty(obj, attr, value):
        current_val = getattr(obj, attr, None)
        if (current_val is None or current_val == "") and (value is not None and value != ""):
            setattr(obj, attr, str(value))

    # Campos conservadores (só preenche se vazio)
    update_if_empty(cliente, 'nome', raw_name)
    update_if_empty(cliente, 'documento', raw_doc)
    update_if_empty(cliente, 'contato_email', raw_email)
    
    # Tenta pegar telefone ou whatsapp
    tel = raw.get('telefoneContato') or raw.get('whatsapp')
    update_if_empty(cliente, 'contato_telefone', tel)
    
    # Campos dinâmicos (sobrescreve sempre)
    # 'ativo' vem como booleano no raw? O script user usa raw.get("ativo")
    val_ativo = raw.get('ativo')
    if val_ativo is not None:
        cliente.ativo = val_ativo
        
    # --- NOVO: Último Acesso ---
    raw_acesso = raw.get('ultimoAcesso')
    if raw_acesso:
        try:
            # Tenta converter string ISO para datetime
            if isinstance(raw_acesso, str):
                # Workaround simples para ISO com Z ou offset
                sanitized = raw_acesso.replace('Z', '+00:00')
                dt = datetime.fromisoformat(sanitized)
                # Converte para naive (ignora tz) para salvar no banco se necessário
                cliente.ultimo_acesso = dt.replace(tzinfo=None)
        except ValueError:
            logging.warning(f"Formato de data invalido para ultimoAcesso: {raw_acesso}")

    # Campos de vínculo técnico
    if s_id: cliente.solarz_id = s_id
    if s_uuid: cliente.solarz_uuid = s_uuid
    
    # Payload
    cliente.solarz_payload = json.dumps(raw)
    cliente.solarz_payload_updated_at = datetime.utcnow()
    cliente.solarz_last_sync_at = datetime.utcnow()
    
    return 'nova' if is_new else 'atualizada'

def registrar_acessos_solarz():
    """
    Processa o campo 'ultimo_acesso' dos clientes para gerar histórico diário.
    Deve ser chamado após o sync de clientes.
    """
    # Busca clientes que tem ID SolarZ e data de acesso
    clientes = Cliente.query.filter(
        Cliente.solarz_id.isnot(None), 
        Cliente.ultimo_acesso.isnot(None)
    ).all()
    
    stats = {"processados": 0, "novos_dias": 0, "atualizados": 0}
    
    for c in clientes:
        if not c.ultimo_acesso:
            continue
            
        stats["processados"] += 1
        data_atual = c.ultimo_acesso.date()
        
        # Busca registro existente para este cliente NESTE dia
        historico = ClienteAcessoSolarz.query.filter_by(
            cliente_id_solarz=c.solarz_id,
            data_ref=data_atual
        ).first()
        
        if not historico:
            # Primeiro registro do dia
            historico = ClienteAcessoSolarz(
                cliente_id_solarz=c.solarz_id,
                data_ref=data_atual,
                ultimo_acesso_detectado=c.ultimo_acesso,
                qtd_acessos_estimados=1
            )
            db.session.add(historico)
            stats["novos_dias"] += 1
        else:
            # Já existe registro hoje. Verifica se houve login novo.
            # Se o timestamp atual do cliente for MAIOR que o último detectado hoje, incrementa.
            if historico.ultimo_acesso_detectado and c.ultimo_acesso > historico.ultimo_acesso_detectado:
                historico.ultimo_acesso_detectado = c.ultimo_acesso
                historico.qtd_acessos_estimados += 1
                stats["atualizados"] += 1
                
    try:
        db.session.commit()
    except Exception as e:
        logging.error(f"Erro ao salvar analytics acessos: {e}")
        db.session.rollback()
        
    return stats
