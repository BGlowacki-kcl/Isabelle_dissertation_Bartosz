import isabelle.{Delay, Time}
import java.util.concurrent.atomic.AtomicBoolean

object DelayBugTest {

  def test_delay_rethrows_exception(): (Boolean, Option[String]) = {
    val firstFired = new AtomicBoolean(false)
    val secondFired = new AtomicBoolean(false)
    var invokeThrew = false

    val d1 = Delay.first(Time.ms(30), gui = false) {
      firstFired.set(true)
      throw new RuntimeException("deliberate exception in delay event")
    }
    d1.invoke()
    Thread.sleep(150)

    val d2 = Delay.first(Time.ms(30), gui = false) {
      secondFired.set(true)
    }
    try {
      d2.invoke()
    } catch {
      case _: IllegalStateException => invokeThrew = true
    }
    Thread.sleep(150)

    val reason =
      if (invokeThrew)
        Some("d2.invoke() threw IllegalStateException — timer thread is dead, Timer already cancelled")
      else if (firstFired.get() && !secondFired.get())
        Some("d1 fired but d2 never did — timer thread died after d1's rethrown exception, no more tasks can run")
      else
        None

    (reason.isDefined, reason)
  }

  def main(args: Array[String]): Unit = {
    println("=" * 60)
    println("  DelayBugTest — Delay.run() rethrow kills event timer")
    println("=" * 60)

    val (bugDetected, reason) = test_delay_rethrows_exception()

    if (bugDetected)
      println(s"  [FAIL] delay_rethrows_exception — bug confirmed\n         Reason: ${reason.get}")
    else
      println("  [PASS] delay_rethrows_exception — no bug detected")

    println("=" * 60)
    System.exit(0)
  }
}
