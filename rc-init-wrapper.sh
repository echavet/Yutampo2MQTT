# rc-init-wrapper.sh
#!/bin/sh -e
exec /run/s6/basedir/scripts/rc.init top /app/run.sh 2>&1 | tee /var/log/yutampo.log