# Packing and minifying of our JavaScript codebase
#
# URL to a minifier:
# http://www.crockford.com/javascript/jsmin.html
#
# Author:	Pontus Stenetorp	<pontus stenetorp se>
# Version:	2011-07-01

# Path to a JavaScript-Minifier executable
JSMIN_BIN=~/jsmin

CLIENT_DIR=client
CLIENT_SRC_DIR=${CLIENT_DIR}/src
CLIENT_LIB_DIR=${CLIENT_DIR}/lib

# These ones are order dependent
LIB_FILES = ${CLIENT_LIB_DIR}/jquery.min.js \
			${CLIENT_LIB_DIR}/jquery-ui.min.js \
			${CLIENT_LIB_DIR}/jquery.svg.min.js \
			${CLIENT_LIB_DIR}/jquery.svgdom.min.js \
			${CLIENT_LIB_DIR}/jquery.ba-bbq.min.js \
			${CLIENT_LIB_DIR}/jquery.sprintf.js \
			${CLIENT_LIB_DIR}/jquery.json.min.js \
			${CLIENT_LIB_DIR}/jquery-ui.min.js

PACKED_LIB=${CLIENT_LIB_DIR}/pack.js
PACKED_LIB_MIN=${CLIENT_LIB_DIR}/pack.min.js

# These ones are order dependent
SRC_FILES = ${CLIENT_SRC_DIR}/util.js \
			${CLIENT_SRC_DIR}/dispatcher.js \
			${CLIENT_SRC_DIR}/url_monitor.js \
			${CLIENT_SRC_DIR}/ajax.js \
			${CLIENT_SRC_DIR}/visualizer.js \
			${CLIENT_SRC_DIR}/visualizer_ui.js \
			${CLIENT_SRC_DIR}/annotator_ui.js \
			${CLIENT_SRC_DIR}/spinner.js

PACKED_SRC=${CLIENT_SRC_DIR}/pack.js
PACKED_SRC_MIN=${CLIENT_SRC_DIR}/pack.min.js

.PHONY: all
all: lib src

.PHONY: lib
lib: ${PACKED_LIB} ${PACKED_LIB_MIN}

.PHONY: src
src: ${PACKED_SRC} ${PACKED_SRC_MIN}

${PACKED_LIB}: ${LIB_FILES}
	rm -f ${PACKED_LIB}
	cat ${LIB_FILES} > ${PACKED_LIB}

${PACKED_LIB_MIN}: ${PACKED_LIB}
	rm -f ${PACKED_LIB_MIN}
	cat ${PACKED_LIB} | ${JSMIN_BIN} > ${PACKED_LIB_MIN}

${PACKED_SRC}: ${SRC_FILES}
	rm -f ${PACKED_SRC}
	cat ${SRC_FILES} > ${PACKED_SRC}

${PACKED_SRC_MIN}: ${PACKED_SRC}
	rm -f ${PACKED_SRC_MIN}
	cat ${PACKED_SRC} | ${JSMIN_BIN} > ${PACKED_SRC_MIN}

.PHONY: clean
clean:
	rm -f ${PACKED_LIB} ${PACKED_LIB_MIN} ${PACKED_SRC} ${PACKED_SRC_MIN}
