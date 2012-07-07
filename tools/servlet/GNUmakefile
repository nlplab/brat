# Not an ant file for producing a brat servlet WAR.
# 
# Author:	Pontus Stenetorp	<pontus stenetorp se>
# Version:	2012-07-29

BRAT_WAR=brat.war
SERVLET_DIR=brat
META_DIR=${SERVLET_DIR}/META-INF
WEB_DIR=${SERVLET_DIR}/WEB-INF

${BRAT_WAR}: ${META_DIR}/context.xml ${WEB_DIR}/web.xml ${shell find ${SERVLET_DIR}}
	jar -cf ${BRAT_WAR} -C ${SERVLET_DIR} .

.PHONY: clean
clean:
	rm -f ${BRAT_WAR}
