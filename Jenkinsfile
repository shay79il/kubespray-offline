@Library('pipelinex@development') _

def buildContainer(distro, tag) {
    docker_file = "Dockerfile_${distro}"
    image_name = "devops/${distro}_kubespray_builder:${tag}"
    common.shell(['podman', 'build', '-t', image_name, '-f', docker_file, '.'])
} // Closes function definition

def runContainer(distro, tag) {
    image_name = "devops/${distro}_kubespray_builder:${tag}"
    sh "mkdir -p \$(pwd)/${distro}_outputs"
    sh "podman run --privileged --net=host -v \$(pwd)/${distro}_outputs:/outputs -v /run/user/1000/podman/podman.sock:/run/podman/podman.sock ${image_name} || exit 1"
    common.shell(['podman', 'rm', '-f', image_name])
    common.shell(['podman', 'rmi', '-f', image_name])
} // Closes function definition

def cleanupRegistryPort() {
    sh '''
        podman rm -f $(podman ps -aq --filter 'name=k8s_registry_') 2>/dev/null || true
        sudo podman rm -f $(sudo podman ps -aq --filter 'name=k8s_registry_') 2>/dev/null || true
        if command -v fuser >/dev/null 2>&1; then
            sudo fuser -k 5000/tcp 2>/dev/null || true
        fi
        sleep 1
    '''
} // Closes function definition

def startRegistry(tag) {
    // Rootless podman --net=host does not share the host loopback with the builder
    // container. Use rootful podman on real :5000. Stale rootless k8s_registry_*
    // containers from prior builds also bind :5000 and steal pushes while the sudo
    // container stays empty (catalog looks full, docker_registry is not).
    cleanupRegistryPort()
    sh """
        rm -rf docker_registry && mkdir -p docker_registry
        sudo podman run --network=host -d \\
            -e REGISTRY_HTTP_ADDR=0.0.0.0:5000 \\
            -v \$(pwd)/docker_registry:/var/lib/registry:Z \\
            --name k8s_registry_${tag} \\
            registry:2
        for i in \$(seq 1 30); do
            curl -sf http://127.0.0.1:5000/v2/ >/dev/null && break
            sleep 1
        done
        curl -sf http://127.0.0.1:5000/v2/ || { echo 'ERROR: registry not reachable on :5000'; exit 1; }
        if curl -sf http://127.0.0.1:5000/v2/_catalog | grep -q calico; then
            echo 'ERROR: registry catalog not empty at start; stale :5000 listener still active'
            curl -sf http://127.0.0.1:5000/v2/_catalog || true
            sudo podman ps -a || true
            podman ps -a || true
            exit 1
        fi
        echo "Registry started clean on :5000 (k8s_registry_${tag})"
    """
} // Closes function definition

def stopRegistry(tag) {
    sh """
        curl -sf http://127.0.0.1:5000/v2/_catalog || echo 'WARN: could not read registry catalog'
        sudo podman exec k8s_registry_${tag} du -sh /var/lib/registry || true
        du -sh ./docker_registry || true
        sudo podman rm -f k8s_registry_${tag} || true
        sudo chown -R iguazio:iguazio ./docker_registry
    """
} // Closes function definition

def config = common.get_config()

def props = [
        buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '30', numToKeepStr: '1000'))
    ]

if (config.cron.get(env.BRANCH_NAME)) {
    props.add(pipelineTriggers([cron(config.cron.get(env.BRANCH_NAME))]))
}

properties(props)

common.main {
    nodes.builder('kubespray-builder') {
        timestamps {

            stage('checkout') {
                sh "sudo rm -rf ${WORKSPACE}/*"
                final scm_vars = checkout scm

                env.kubespray_hash = scm_vars.GIT_COMMIT
                currentBuild.description = "branch ${env.BRANCH_NAME}, ${env.kubespray_hash}"
            }

            stage('apply pre-build igz patches and start registry') {
                dir('./') {
                    sh("igz_files/igz_prebuild_patch.sh")
		    startRegistry(env.kubespray_hash)
                } // closes dir
            } // closes stage

            stage('build') {
                try {
                    dir('./') {
                        buildContainer('rocky8', env.kubespray_hash)
                        runContainer('rocky8', env.kubespray_hash)
                    } // closes dir
                } catch (Exception e) {
                    println "An error occurred: ${e.getMessage()}"
                    stopRegistry(env.kubespray_hash)
                    throw e // Rethrow the exception to mark the build as failed
                }
            } // closes stage

            stage('merge assets and build ansible container') {
                dir('./') {
		            stopRegistry(env.kubespray_hash)
                    sh('''if [ "$(find docker_registry -mindepth 1 -print -quit 2>/dev/null | wc -l)" -eq 0 ]; then
                        echo "ERROR: docker_registry is empty after offline build; image pushes did not persist"
                        exit 1
                    fi
                    echo "docker_registry size: $(du -sh docker_registry)"''')
                    sh("echo 'So here we are'")
                    sh("ls -la")
		            sh('sudo chown -R 1000:1000 rocky8_outputs')
                    sh("mv rocky8_outputs/rpms rocky8_outputs/rocky8_rpms")
		            sh("mv ./docker_registry rocky8_outputs/")
                    sh("rm -rf outputs")
                    sh("mv rocky8_outputs outputs")
                    sh("igz_files/igz_build_ansible.sh")
                } // closes dir
            } // closes stage

            stage('upload assets') {
                parallel(
                    'upload_to_nas': {
                        def build_by_hash_dir = "/mnt/nas/build_by_hash/kubespray"
                        def nas_dir = "${build_by_hash_dir}/${env.kubespray_hash}/pkg/kubespray"
                        sh("if [ -d ${nas_dir} ]; then sudo rm -rf ${nas_dir}; fi")
                        sh("mkdir -p ${nas_dir}")
                        sh("cp -r outputs ${nas_dir}/")
                    }, // closes upload_to_nas block
                    'upload_to_s3': {
                        def bucket = 'iguazio-versions'
                        def bucket_region = 'us-east-1'
                        common.upload_to_s3(bucket, bucket_region, 'outputs', "build_by_hash/kubespray/${env.kubespray_hash}/pkg/kubespray/outputs")
                    } // closes upload_to_s3 block
                ) // closes parallel list
            } // closes stage
        } // closes timestamps 
    } // closes builders
} // closes common.main
