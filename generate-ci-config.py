import yaml
import os

mode = os.environ['mode']
print(mode)

my_yaml = {'image': 'docker/compose:latest',
           'tags': ['dora'],
           'secret_id': 'google_id_env_dora',
           'secret_secret': 'google_secret_env_dora',
           'environment': 'production',
           'stages': []}

def build_script(action, in_pipe, in_full):
  dockerprefix = f'docker-compose -f docker-compose.{in_pipe}.yml'
  suffix=''
  if 'test' in in_pipe:
    suffix='test'
  my_env = my_yaml['environment']
  my_machine = my_yaml['tags'][0]
  secret_id = my_yaml['secret_id']
  secret_secret = my_yaml['secret_secret']
  def make_before_statement(in_action, in_service):
    return [f'echo "{in_action.capitalize()}ing the {my_env} {in_service} on {my_machine}..."']
  def make_after_statement(in_action_past, in_service):
    return [f'echo "{my_env.capitalize()} {in_service} successfully {in_action_past} {my_machine}."']
  script = ['docker info'] + ['docker-compose --version']
  match action:
    case "shutdown":
      match in_full:
        case "webapp":
          return [f'{dockerprefix} rm -f -s webapp{suffix}']
        case "full":
          return [f'{dockerprefix} down']
    case "stop":
      match in_full:
        case "webapp":
          return [f'{dockerprefix} stop webapp{suffix}']
        case "full":
          return [f'{dockerprefix} down']
    case "build":
      match in_full:
        case "webapp":
          build_before_statement = make_before_statement('build', 'webapp')
          build_after_statement = make_after_statement('built on', 'webapp')
          build_statement = [f'{dockerprefix} build webapp{suffix}']
        case "full":
          build_before_statement = make_before_statement('build', 'webapp and database application')
          build_after_statement = make_after_statement('built on', 'webapp and database application')
          build_statement = ['docker run -d --name mytmpsource -v baksql:/source -w /source alpine ls']
          build_statement += ['docker cp mytmpsource:/source/backup.sql /builds/john.krasting/dora/mariadb/']
          build_statement += ['docker stop mytmpsource']
          build_statement += ['docker rm mytmpsource']
          build_statement += [f'{dockerprefix} build']
      script += build_before_statement
      script += ['sed -i \'s/google_id_env_dora/\'${' + secret_id + '}\'/\' .env']
      script += ['sed -i \'s/google_secret_env_dora/\'${' + secret_secret + '}\'/\' .env']
      script += build_statement
      script += build_after_statement
      return script
      
    case "start":
      script += make_before_statement('start', 'webapp')
      script += [f'{dockerprefix} start webapp{suffix}']
      script += make_after_statement('restarted on', 'webapp')
      return script

    case "deploy":
      script += make_before_statement('deploy', 'webapp and database application')
      script += [f'{dockerprefix} up -d']
      script += make_after_statement('deployed to', 'webapp and database application')
      return script

def build_job_dict(action, in_yaml, in_pipeline, full='webapp'):
  in_yaml['stages'].append(action)
  in_yaml[f'{action}-job'] = {'stage': action, 'script': build_script(action, in_pipeline, full)}
  in_yaml[f'{action}-job'] = in_yaml[f'{action}-job'] 
  del in_yaml[f'{action}-job']['secret_id'] 
  del in_yaml[f'{action}-job']['secret_secret'] 
  return in_yaml
  
match mode.split('-'):
  case ["shutdown", pipeline]:
      my_yaml = build_job_dict('shutdown', my_yaml, pipeline)
  case ["shutdownfull", pipeline]:
      my_yaml = build_job_dict('shutdown', my_yaml, pipeline, full='full')
  case ["build", pipeline]:
      my_yaml = build_job_dict('build', my_yaml, pipeline)
  case ["buildfull", pipeline]:
      my_yaml = build_job_dict('build', my_yaml, pipeline, full='full')
  case ["deploy", pipeline]:
      my_yaml = build_job_dict('deploy', my_yaml, pipeline)
  case ["reset", pipeline]:
      my_yaml = build_job_dict('stop', my_yaml, pipeline)
      my_yaml = build_job_dict('start', my_yaml, pipeline)
  case ["standard", pipeline]:
      my_yaml = build_job_dict('shutdown', my_yaml, pipeline)
      my_yaml = build_job_dict('build', my_yaml, pipeline)
      my_yaml = build_job_dict('deploy', my_yaml, pipeline)
  case ["completefull", pipeline]:
      my_yaml = build_job_dict('shutdown', my_yaml, pipeline, full='full')
      my_yaml = build_job_dict('build', my_yaml, pipeline, full='full')
      my_yaml = build_job_dict('deploy', my_yaml, pipeline)
  case _:
    raise KeyError('Unidentified mode provided')

with open('generated-config.yml','w') as fh:
  yaml.dump(my_yaml,fh,default_flow_style=False)

