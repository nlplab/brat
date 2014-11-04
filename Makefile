# Makefile for Jekyll interactions that we can't be bothered to remember.

# From: https://help.github.com/articles/using-jekyll-with-pages
.PHONY: serve
serve:
	bundle exec jekyll serve --watch

.PHONY: imgopt
imgopt:
	find img -iname '*.jpg' | xargs -r jpegoptim
	find img -iname '*.png' | xargs -r optipng

# Necessary tools to build the homepage.
.PHONY: install
install:
	sudo apt-get install jpegoptim optipng ruby ruby-dev
	sudo gem install bundler
	bundle install

.PHONY: update
update:
	bundle update
