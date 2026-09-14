terraform {
  required_version = ">= 1.10.0, < 2.0.0"

  required_providers {
    fleets = {
      source  = "trycua/fleets"
      version = "0.3.0"
    }
  }
}

provider "fleets" {
  endpoint = "https://run.cua.ai"
}

resource "fleets_pool" "gameworld_autoresearch" {
  name                 = "gameworld-autoresearch"
  cpu_cores            = 4
  memory               = "16384Mi"
  container_disk_image = "ghcr.io/trycua/gameworld-autoresearch@sha256:1cd6a89f71728c8cb31b6ed550f98ab92388d1e75e4a4598cba6f60ec867bf82"
  runtime              = "gvisor"
  readiness_probe_json = jsonencode({ tcpSocket = { port = 8000 } })

  service {
    name        = "server"
    target_port = 8000
    protocol    = "TCP"
  }

  service {
    name        = "novnc"
    target_port = 6080
    protocol    = "TCP"
  }

  autoscaling {
    min_pool_size     = 0
    initial_pool_size = 0
    max_pool_size     = 20
  }
}

output "pool" {
  value = {
    name             = fleets_pool.gameworld_autoresearch.name
    namespace        = fleets_pool.gameworld_autoresearch.namespace
    template_name    = fleets_pool.gameworld_autoresearch.template_name
    current_replicas = fleets_pool.gameworld_autoresearch.current_replicas
    ready_replicas   = fleets_pool.gameworld_autoresearch.ready_replicas
  }
}
