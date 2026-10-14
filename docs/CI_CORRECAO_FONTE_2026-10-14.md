# Correção do build GitHub — 14/10/2026

Execução analisada: https://github.com/arturcardoalves/Urna-Eletronica-Escolar/actions/runs/38508810576

O job falhou antes da compilação: `test_both_qrs_decode_inside_actual_thermal_document` dependia da fonte Atkinson instalada no Windows. O runner não tinha essa fonte: 99 testes passaram e um falhou. O aviso de Node.js 20 foi apenas um aviso, com execução das actions forçada em Node 24; não foi a causa da interrupção.

Correção em `tests/test_publication.py`: o teste de posicionamento e decodificação dos QR Codes agora utiliza explicitamente uma fonte de teste do Pillow no mesmo renderizador térmico de 576 pontos. A ausência da fonte do Windows é simulada para evitar que uma instalação local esconda a falha do runner. A exigência de Atkinson na impressão real não foi alterada. Tipografia e papel físico continuam dependendo de validação no equipamento.

Os testes da demonstração restauram a seleção de fonte após cada teste, sem mudar a impressão oficial dentro do mesmo processo do pytest.

Validação local: **103 testes passaram**, sem falhas ou skips; `test-results/github-build-regression.xml`. Os bancos, entradas de teclado e drivers de teste são isolados/simulados. A nova execução no GitHub depende do envio deste commit; repetir o job antigo não carrega as alterações locais.

Também estão preparados para envio os arquivos da demonstração com teclado visual e QR Codes. O workflow gera o artefato separado **Urna-Escolar-Teste-Ficticio**; o instalador oficial não carrega automaticamente esses dados fictícios.
