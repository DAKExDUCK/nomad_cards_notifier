#!/usr/bin/env bash

set -euo pipefail

IMAGE_NAME="dakexduck/nomad_cards_notifier"
TAG="latest"
PUSH=false

usage() {
	cat <<EOF
Usage: $0 [options]

Options:
  -t, --tag TAG    Docker image tag (default: latest)
	  --push       Push the image after a successful build
  -h, --help       Show this help
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		-t|--tag)
			if [[ $# -lt 2 || -z "$2" ]]; then
				echo "Error: --tag requires a value" >&2
				exit 2
			fi
			TAG="$2"
			shift 2
			;;
		--push)
			PUSH=true
			shift
			;;
		-h|--help)
			usage
			exit 0
			;;
		*)
			echo "Error: unknown option: $1" >&2
			usage >&2
			exit 2
			;;
	esac
done

IMAGE="${IMAGE_NAME}:${TAG}"

echo "Building ${IMAGE}..."
docker build -t "$IMAGE" .

if [[ "$PUSH" == true ]]; then
	echo "Pushing ${IMAGE}..."
	docker push "$IMAGE"
fi
