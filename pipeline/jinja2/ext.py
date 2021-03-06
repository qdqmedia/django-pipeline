from __future__ import unicode_literals

from django.contrib.staticfiles.storage import staticfiles_storage

from django.conf import settings
from jinja2 import Environment, FileSystemLoader
from pipeline.packager import Packager, PackageNotFound
from pipeline.utils import guess_type


class Jinja2Compressed(object):
    def __init__(self, package_type):
        from django.template.loaders import app_directories
        if package_type not in ['css', 'js']:
            raise PackageNotFound("Package type must be css or js, supplied %s" % package_type)
        self.package_type = package_type
        self.loader = FileSystemLoader((app_directories.app_template_dirs +
                                        settings.TEMPLATE_DIRS))

    def get_package(self, name):
        """Get the js or css package."""
        package = {
            'js': settings.PIPELINE_JS.get(name, {}),
            'css': settings.PIPELINE_CSS.get(name, {}),
        }[self.package_type]

        if package:
            package = {name: package}

        self.packager = {
            'js': Packager(css_packages={}, js_packages=package),
            'css': Packager(css_packages=package, js_packages={}),
        }[self.package_type]

        try:
            self.package = self.packager.package_for(self.package_type, name)
        except PackageNotFound:
            self.package = None

    def render(self, path):
        """Render the HTML tag."""
        if not self.package.template_name:
            template_name = {
                'js': 'pipeline/js.jinja',
                'css': 'pipeline/css.jinja',
            }[self.package_type]
        else:
            template_name = self.package.template_name

        mimetype = {
            'js': 'text/javascript',
            'css': 'text/css',
        }[self.package_type]

        context = self.package.extra_context
        context.update({
            'type': guess_type(path, mimetype),
            'url': staticfiles_storage.url(path)
        })

        env = Environment(loader=self.loader)
        tpl = env.get_template(template_name)
        return tpl.render(**context)

    def html(self, name):
        """Render the HTML Snippet"""
        self.get_package(name)
        if self.package:
            if not settings.DEBUG:
                return self.render(self.package.output_filename)
            else:
                paths = self.packager.compile(self.package.paths)
                templates = self.packager.pack_templates(self.package)
                return {
                    'css': self.render_individual_css(paths),
                    'js': self.render_individual_js(paths, templates)
                }[self.package_type]
        else:
            return ''  # don't return anything if no package found

    def render_individual_css(self, paths):
        """Render individual CSS files"""
        tags = [self.render(path) for path in paths]
        return '\n'.join(tags)

    def render_individual_js(self, paths, templates=None):
        """Render individual JS files"""
        tags = [self.render(path) for path in paths]
        if templates:
            tags.append(self.render_inline_js(self.package, templates))
        return '\n'.join(tags)

    def render_inline_js(self, package, js):
        template_name = (self.package.template_name or
                         "pipeline/inline_js.jinja")
        context = self.package.extra_context
        context.update({
            'source': js
        })
        env = Environment(loader=self.loader)
        tpl = env.get_template(template_name)
        return tpl.render(**context)


def compressed_css(package_name):
    compress = Jinja2Compressed('css')
    return compress.html(package_name)


def compressed_js(package_name):
    compress = Jinja2Compressed('js')
    return compress.html(package_name)
