# Ariston NET + Siri (versão simples)

## 1. Antes de publicar
1. Muda a palavra-passe da conta Ariston NET.
2. Se o repositório antigo esteve público, apaga-o ou torna-o privado.

## 2. GitHub (pelo site, sem comandos)
1. github.com, "New repository", nome ariston-siri, Private, sem README.
2. Link "uploading an existing file", "choose your files".
3. Escolhe: ariston_server.py, render.yaml, requirements.txt, LEIAME.md. "Commit changes".

## 3. Render
1. "New", depois "Blueprint" (importante: não "Web Service").
2. Liga o repositório ariston-siri.
3. O Render pede o ARISTON_USERNAME e a ARISTON_PASSWORD (a nova). A API_KEY é gerada sozinha.
4. Quando terminar, abre o serviço, separador Environment, e copia o valor da API_KEY.
5. Guarda também o endereço do serviço, algo como https://ariston-server-xxxx.onrender.com

## 4. Testar
Abre no browser: ENDEREÇO/health
Deve dizer connected true (pode demorar um minuto na primeira vez).
Depois: ENDEREÇO/status?api_key=A_TUA_CHAVE

## 5. Atalho na app Atalhos
1. Novo atalho. Dá-lhe o nome que queres dizer à Siri, por exemplo "estado do termoacumulador".
2. Ação "Obter conteúdo de URL", com o endereço:
   ENDEREÇO/status?api_key=A_TUA_CHAVE
3. Ação "Falar texto", com o resultado da ação anterior.
4. Para os outros, duplica o atalho e muda só a parte do meio:
   /temp, /target, /boost, /eco/on, /eco/off, /power/on, /power/off,
   /mode/program, /temp/up, /temp/down, /temp/set/55

## 6. Plano gratuito
O serviço adormece após cerca de 15 minutos sem uso, e o primeiro pedido demora.
Solução: UptimeRobot a chamar ENDEREÇO/health a cada 5 a 10 minutos.
