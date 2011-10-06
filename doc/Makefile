# Makefile for generating stav documentation and documentation related files.
#
# Author:	Pontus Stenetorp	<pontus stenetorp se>
# Version:	2011-07-14

CLIENT_SERVER_INIT=client_server_init

EXPORT_WIDTH=400

.PHONY: all
all: ${CLIENT_SERVER_INIT}.svg ${CLIENT_SERVER_INIT}.pdf ${CLIENT_SERVER_INIT}.png

${CLIENT_SERVER_INIT}.svg: ${CLIENT_SERVER_INIT}.msc
	mscgen -T svg ${CLIENT_SERVER_INIT}.msc
	
${CLIENT_SERVER_INIT}.pdf: ${CLIENT_SERVER_INIT}.svg
	inkscape -z --file="${CLIENT_SERVER_INIT}.svg" \
		--export-pdf="${CLIENT_SERVER_INIT}.pdf"

${CLIENT_SERVER_INIT}.png: ${CLIENT_SERVER_INIT}.svg
	inkscape -z --file="${CLIENT_SERVER_INIT}.svg" \
		--export-png="${CLIENT_SERVER_INIT}.png" \
		--export-width=${EXPORT_WIDTH}

clean:
	-rm -f *.svg *.pdf *.png
