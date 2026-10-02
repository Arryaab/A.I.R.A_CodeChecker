class BatchNorm1D:
    def __init__(self, momentum=0.1):
        self.running_mean = 0.0
        self.momentum = momentum
        self.training = True

    def forward(self, batch_mean: float):
        # BUG: updates running_mean even when self.training is False
        self.running_mean = (1 - self.momentum) * self.running_mean + self.momentum * batch_mean
        return self.running_mean
