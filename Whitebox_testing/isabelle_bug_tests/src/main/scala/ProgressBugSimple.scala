import isabelle.{Exn, Future, Progress, Time}

object ProgressBugSimple {

  def testA(): Boolean = {
    val progress = new Progress()
    try {
      progress.bash("sleep 0.01", watchdog_time = Time.seconds(0.001))
    } catch {
      case _: Throwable => // gracefully ignore the bash timeout exception
    }
    Thread.sleep(10) // let interrupt propagate
    
    // Optional: Clear the interrupt flag
    // Thread.interrupted() 
    
    progress.stopped
  }

  def testB(): Boolean = {
    val f = Future.fork { Range(1, 1000).map { _ => new Progress().stopped } }
    f.cancel()
    Exn.is_exn(f.join_result)
  }

  def runUntilBug(name: String, iterations: Int)(test: => Boolean): Option[Int] = {
    var i = 0
    var hitAt: Option[Int] = None
    while (i < iterations && hitAt.isEmpty) {
      i += 1
      if (test) {
        hitAt = Some(i)
      } else if (i % 100 == 0) {
        println(s"  [$name] iter $i / $iterations — no bug yet")
      }
    }
    hitAt
  }

  def main(args: Array[String]): Unit = {
    val iterations = 10000
    println("=" * 60)
    println(s"  ProgressBugSimple — up to $iterations iterations each")
    println("=" * 60)

    println(s"\n--- TEST A: watchdog sets stopped ---")
    val hitA = runUntilBug("TEST A", iterations)(testA())
    hitA match {
      case Some(n) => println(s"FAILED: TEST A bug triggered at iteration $n")
      case None    => println(s"PASSED: TEST A: no bug in $iterations iterations")
    }

    println(s"\n--- TEST B: Future.cancel leaks interrupt ---")
    val hitB = runUntilBug("TEST B", iterations)(testB())
    hitB match {
      case Some(n) => println(s"FAILED: TEST B bug triggered at iteration $n")
      case None    => println(s"PASSED: TEST B: no bug in $iterations iterations")
    }

    System.exit(0)
  }
}
