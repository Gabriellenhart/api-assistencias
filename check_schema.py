"""
Quick script to check database schema and test validation endpoint
"""
import sys
sys.path.insert(0, '.')

from api import create_app, db
from api.models import Usuario, Chamado, ConfiguracaoOperacional
from sqlalchemy import inspect

app = create_app()

with app.app_context():
    # Check Usuario table columns
    print("=" * 50)
    print("VERIFICANDO SCHEMA DA TABELA USUARIOS")
    print("=" * 50)
    
    inspector = inspect(db.engine)
    columns = inspector.get_columns('usuarios')
    
    required_columns = ['horario_inicio', 'horario_fim', 'latitude_base', 'longitude_base']
    
    print("\nColunas existentes:")
    for col in columns:
        print(f"  - {col['name']} ({col['type']})")
    
    print("\nVerificando colunas necessárias:")
    for req_col in required_columns:
        exists = any(col['name'] == req_col for col in columns)
        status = "✓" if exists else "✗"
        print(f"  {status} {req_col}")
    
    # Check if any columns are missing
    missing = [col for col in required_columns if not any(c['name'] == col for c in columns)]
    
    if missing:
        print(f"\n⚠️  COLUNAS FALTANDO: {', '.join(missing)}")
        print("\nSolução: Execute 'flask db upgrade' para aplicar migrations")
    else:
        print("\n✓ Todas as colunas necessárias existem!")
    
    # Check ConfiguracaoOperacional table
    print("\n" + "=" * 50)
    print("VERIFICANDO TABELA CONFIGURACAO_OPERACIONAL")
    print("=" * 50)
    
    try:
        config_columns = inspector.get_columns('configuracao_operacional')
        print(f"\n✓ Tabela existe com {len(config_columns)} colunas")
        
        config = ConfiguracaoOperacional.query.first()
        if config:
            print(f"✓ Configuração padrão existe (ID: {config.id})")
        else:
            print("⚠️  Nenhuma configuração encontrada. Será criada automaticamente.")
    except Exception as e:
        print(f"✗ Erro ao verificar tabela: {e}")
    
    # Check sample Usuario
    print("\n" + "=" * 50)
    print("VERIFICANDO USUÁRIOS")
    print("=" * 50)
    
    usuarios = Usuario.query.limit(3).all()
    if usuarios:
        print(f"\nEncontrados {len(usuarios)} usuários (mostrando até 3):")
        for user in usuarios:
            print(f"\n  ID: {user.id}")
            print(f"  Nome: {user.nome}")
            print(f"  Horário início: {user.horario_inicio if hasattr(user, 'horario_inicio') else 'N/A'}")
            print(f"  Horário fim: {user.horario_fim if hasattr(user, 'horario_fim') else 'N/A'}")
            print(f"  Latitude base: {user.latitude_base if hasattr(user, 'latitude_base') else 'N/A'}")
            print(f"  Longitude base: {user.longitude_base if hasattr(user, 'longitude_base') else 'N/A'}")
    else:
        print("⚠️  Nenhum usuário encontrado")
    
    # Check Chamados
    print("\n" + "=" * 50)
    print("VERIFICANDO CHAMADOS")
    print("=" * 50)
    
    chamados_count = Chamado.query.count()
    print(f"\nTotal de chamados: {chamados_count}")
    
    if chamados_count > 0:
        sample = Chamado.query.first()
        print(f"\nExemplo de chamado (ID: {sample.id_chamado}):")
        print(f"  Cliente: {sample.cliente.nome if sample.cliente else 'N/A'}")
        print(f"  Tempo estimado: {sample.tempo_estimado_minutos if hasattr(sample, 'tempo_estimado_minutos') else 'N/A'} min")
        print(f"  KM estimado: {sample.km_estimado if hasattr(sample, 'km_estimado') else 'N/A'} km")
        if sample.usina:
            print(f"  Usina: {sample.usina.nome}")
            print(f"  Coordenadas: {sample.usina.latitude}, {sample.usina.longitude}")

print("\n" + "=" * 50)
print("VERIFICAÇÃO CONCLUÍDA")
print("=" * 50)
