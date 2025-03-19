# rc-init-wrapper.sh
#!/bin/sh -e
exec /run/s6/basedir/scripts/rc.init top /app/run.sh 2>&1 | s6-fdholder-store /run/s6-rc/fdholder yutampo-log