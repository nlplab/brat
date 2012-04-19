# Quick makefile hack to install dependencies etc.

CORENLP_VER=stanford-corenlp-2012-04-09
CORENLP_ARCH=${CORENLP_VER}.tgz
CORENLP_URL=http://nlp.stanford.edu/software/${CORENLP_ARCH}
CORENLP_SH=${CORENLP_ARCH}/corenlp.sh

prepare: ${CORENLP_SH} pexpect

${CORENLP_ARCH}:
	wget -O ${CORENLP_ARCH} ${CORENLP_URL}

${CORENLP_SH}: ${CORENLP_ARCH}
	tar -x -z -f ${CORENLP_ARCH}

# A bit of a hack, but ensures that we have pexpect
.PHONY: pexpect
pexpect:
	python -c 'import pexpect' || sudo pip install pexpect

.PHONY: clean
clean:
	rm -rf ${CORENLP_VER} ${CORENLP_ARCH}
