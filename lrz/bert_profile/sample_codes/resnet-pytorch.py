import torch
import torch.nn
import torch.optim
import torch.profiler
import torch.utils.data
import torchvision.datasets
import torchvision.models
import torchvision.transforms as T

transform = T.Compose(
    [T.Resize(224),
     T.ToTensor(),
     T.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))])
train_set = torchvision.datasets.CIFAR10(root='./data', train=True, download=True, transform=transform)
train_loader = torch.utils.data.DataLoader(train_set, batch_size=32, shuffle=True)

device = torch.device('cpu')
model = torchvision.models.resnet18(pretrained=True).to(device)#.cuda(device)
# model.fc = torch.nn.Sequential(*list(model.fc)+[torch.nn.Softmax(1)])
criterion = torch.nn.CrossEntropyLoss().to(device)#.cuda(device)
optimizer = torch.optim.SGD(model.parameters(), lr=0.001, momentum=0.9)
model.train()

print(model)

def train(data):
    inputs, labels = data[0].to(device=device), data[1].to(device=device)
    outputs = model(inputs)
    loss = criterion(outputs, labels)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

prof = torch.profiler.profile(
        activities=[torch.profiler.ProfilerActivity.CPU],
        schedule=torch.profiler.schedule(wait=1, warmup=1, active=3, repeat=2),
        on_trace_ready=torch.profiler.tensorboard_trace_handler('./log/resnet18'),
        record_shapes=True,
        profile_memory=False,
        with_stack=True,
        use_cuda=False)

prof.start()

for step, batch_data in enumerate(train_loader):
    if step >= (1 + 1 + 3) * 2:
        break
    train(batch_data)
    prof.step()

prof.stop()

# with torch.profiler.profile(
#         activities=[torch.profiler.ProfilerActivity.CPU],
#         schedule=torch.profiler.schedule(wait=1, warmup=1, active=3, repeat=2),
#         on_trace_ready=torch.profiler.tensorboard_trace_handler('./log/resnet18'),
#         record_shapes=True,
#         profile_memory=True,
#         with_stack=True
# ) as prof:
#     for step, batch_data in enumerate(train_loader):
#         if step >= (1 + 1 + 3) * 2:
#             break
#         train(batch_data)
#         prof.step()